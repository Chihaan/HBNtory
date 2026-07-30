"""API HTTP publique de l'assistant inventaire."""

import logging
import math
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StringConstraints

from agent import (
    AgentRateLimitError,
    AgentServiceError,
    AgentTimeoutError,
    ask_agent,
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


@app.post("/ask", response_model=Answer)
async def ask(payload: Question) -> Answer:
    """Interroge l'agent et masque les erreurs techniques au client."""
    try:
        answer = await ask_agent(payload.question)
    except AgentRateLimitError as exc:
        logger.warning("Limite temporaire du fournisseur IA atteinte.")
        retry_after = exc.retry_after_seconds
        if retry_after is not None and retry_after > 90:
            minutes = math.ceil(retry_after / 60)
            retry_message = (
                f"Réessayez dans environ {minutes} minutes."
            )
        else:
            retry_message = "Réessayez dans une minute."
        raise HTTPException(
            status_code=429,
            detail=(
                "La limite temporaire du service IA est atteinte. "
                f"{retry_message}"
            ),
        ) from exc
    except AgentTimeoutError as exc:
        logger.warning("Budget de réponse dépassé.")
        raise HTTPException(
            status_code=504,
            detail=(
                "Le service d'assistance a mis trop de temps à répondre. "
                "Reformulez une question plus simple."
            ),
        ) from exc
    except AgentServiceError as exc:
        logger.exception("Échec de l'agent IA : %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Le service d'assistance est temporairement indisponible.",
        ) from exc
    return Answer(answer=answer)


@app.get("/health")
def health() -> dict:
    """Indique que le processus HTTP est prêt à recevoir des requêtes."""
    return {"status": "ok"}
