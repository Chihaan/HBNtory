"""API HTTP publique de l'assistant inventaire."""

import asyncio
import logging
import math
from typing import Annotated

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, StringConstraints, ValidationError

from agent import (
    AgentRateLimitError,
    AgentServiceError,
    AgentTimeoutError,
    MCP_TIMEOUT_SECONDS,
    ask_agent,
    build_mcp_client,
)

# Sans configuration, Python n'émet rien en dessous de WARNING, et
# Uvicorn ne configure que ses propres journaux : rien de ce que nous
# traçons n'apparaîtrait dans `docker compose logs ai-service`. La
# racine reste volontairement à WARNING : les bibliothèques tierces
# (httpx, mcp) journalisent une ligne par requête HTTP, qui noierait
# les nôtres. Chaque module de l'application relève lui-même son propre
# niveau à INFO.
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI(title="HBNtory AI Service")

QuestionText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=1000,
    ),
]


class Question(BaseModel):
    """Question validée envoyée par le client web."""

    question: QuestionText


class Answer(BaseModel):
    """Réponse textuelle retournée au client web."""

    answer: str


def _rate_limit_detail(exc: AgentRateLimitError) -> str:
    """Produit le message public associé à une limite fournisseur."""
    retry_after = exc.retry_after_seconds
    if retry_after is not None and retry_after > 90:
        minutes = math.ceil(retry_after / 60)
        retry_message = f"Réessayez dans environ {minutes} minutes."
    else:
        retry_message = "Réessayez dans une minute."
    return (
        "La limite temporaire du service IA est atteinte. "
        f"{retry_message}"
    )


def _public_agent_error(exc: AgentServiceError) -> str:
    """Traduit une erreur d'agent sans exposer de détail technique."""
    if isinstance(exc, AgentRateLimitError):
        return _rate_limit_detail(exc)
    if isinstance(exc, AgentTimeoutError):
        return (
            "Le service d'assistance a mis trop de temps à répondre. "
            "Reformulez une question plus simple."
        )
    return "Le service d'assistance est temporairement indisponible."


async def _call_product_tool(name: str, arguments: dict) -> dict:
    """Interroge le Product MCP sans exposer le fournisseur au navigateur."""
    try:
        async with asyncio.timeout(MCP_TIMEOUT_SECONDS + 2):
            async with build_mcp_client() as mcp_client:
                result = await mcp_client.call_tool(
                    name,
                    arguments,
                    timeout=MCP_TIMEOUT_SECONDS,
                )
    except (asyncio.TimeoutError, TimeoutError) as exc:
        logger.warning("Le Product MCP n'a pas répondu à temps.")
        raise HTTPException(
            status_code=504,
            detail="Le catalogue produits a mis trop de temps à répondre.",
        ) from exc
    except Exception as exc:
        logger.exception("Le Product MCP est indisponible.")
        raise HTTPException(
            status_code=503,
            detail="Le catalogue produits est temporairement indisponible.",
        ) from exc

    data = result.data
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Le catalogue produits a retourné une réponse invalide.",
        )
    return data


@app.get("/products")
async def product_catalog() -> dict:
    """Retourne les métadonnées légères utiles aux cartes du CWI."""
    data = await _call_product_tool(
        "products_list_products",
        {"query": "", "limit": 100},
    )
    products = data.get("products")
    if data.get("success") is not True or not isinstance(products, list):
        raise HTTPException(
            status_code=503,
            detail="Le catalogue produits est temporairement indisponible.",
        )
    return {"products": products}


@app.get("/products/{product_id}")
async def product_details(product_id: int) -> dict:
    """Retourne le détail d'un produit sélectionné dans une réponse."""
    data = await _call_product_tool(
        "products_get_product_details",
        {"product_id": product_id},
    )
    product = data.get("product")
    if data.get("success") is not True or not isinstance(product, dict):
        raise HTTPException(
            status_code=404,
            detail="Ce produit est introuvable.",
        )
    return {"product": product}


@app.post("/ask", response_model=Answer)
async def ask(payload: Question) -> Answer:
    """Interroge l'agent et masque les erreurs techniques au client."""
    try:
        answer = await ask_agent(payload.question)
    except AgentRateLimitError as exc:
        logger.warning("Limite temporaire du fournisseur IA atteinte.")
        raise HTTPException(
            status_code=429,
            detail=_public_agent_error(exc),
        ) from exc
    except AgentTimeoutError as exc:
        logger.warning("Budget de réponse dépassé.")
        raise HTTPException(
            status_code=504,
            detail=_public_agent_error(exc),
        ) from exc
    except AgentServiceError as exc:
        logger.exception("Échec de l'agent IA : %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Le service d'assistance est temporairement indisponible.",
        ) from exc
    return Answer(answer=answer)


@app.websocket("/ws")
async def websocket_ask(websocket: WebSocket) -> None:
    """Diffuse les étapes et la réponse au fil de leur production."""
    await websocket.accept()

    while True:
        try:
            data = await websocket.receive_json()
        except WebSocketDisconnect:
            return
        except ValueError:
            await websocket.send_json({
                "type": "error",
                "detail": "Le message envoyé n'est pas un JSON valide.",
            })
            continue

        request_id = data.get("request_id") if isinstance(data, dict) else None
        if not isinstance(request_id, str) or len(request_id) > 100:
            request_id = None

        if not isinstance(data, dict) or data.get("type") != "question":
            await websocket.send_json({
                "type": "error",
                "request_id": request_id,
                "detail": "Le message doit contenir une question.",
            })
            continue

        try:
            payload = Question.model_validate({
                "question": data.get("question"),
            })
        except ValidationError:
            await websocket.send_json({
                "type": "error",
                "request_id": request_id,
                "detail": (
                    "La question doit contenir entre 1 et 1000 caractères."
                ),
            })
            continue

        async def send_event(event: dict) -> None:
            await websocket.send_json({
                **event,
                "request_id": request_id,
            })

        try:
            await ask_agent(payload.question, on_event=send_event)
            await send_event({"type": "done"})
        except AgentServiceError as exc:
            if isinstance(exc, AgentRateLimitError):
                logger.warning(
                    "Limite temporaire du fournisseur IA atteinte."
                )
            elif isinstance(exc, AgentTimeoutError):
                logger.warning("Budget de réponse dépassé.")
            else:
                logger.exception("Échec de l'agent IA : %s", exc)
            await send_event({
                "type": "error",
                "detail": _public_agent_error(exc),
            })


@app.get("/health")
def health() -> dict:
    """Indique que le processus HTTP est prêt à recevoir des requêtes."""
    return {"status": "ok"}
