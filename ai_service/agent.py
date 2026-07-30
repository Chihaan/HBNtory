"""Agent conversationnel utilisant exclusivement les outils MCP du projet."""

import asyncio
import json
import logging
import os
import time
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastmcp import Client
from openai import AsyncOpenAI, RateLimitError

load_dotenv()

# Le suivi d'une question (outils appelés, durées) se trace en INFO,
# sous le seuil WARNING que `app.py` fixe pour la racine.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PRODUCT_MCP_URL = os.getenv(
    "PRODUCT_MCP_URL",
    "http://localhost:8001/mcp",
)
STOCK_MCP_URL = os.getenv(
    "STOCK_MCP_URL",
    "http://localhost:8003/mcp",
)
AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
AI_FALLBACK_MODELS = tuple(
    model.strip()
    for model in os.getenv(
        "AI_FALLBACK_MODELS",
        (
            "openai/gpt-oss-120b,"
            "qwen/qwen3.6-27b,"
            "openai/gpt-oss-20b"
        ),
    ).split(",")
    if model.strip()
)

# Budget de bout en bout d'une question. Les trois couches sont
# volontairement croissantes :
#   AI Service 60 s  <  Nginx proxy_read_timeout 75 s  <  navigateur 90 s
# La couche la plus interne coupe donc toujours en premier et renvoie un
# message français clair, au lieu d'un 504 brut de Nginx ou d'un onglet
# qui tourne indéfiniment. Toute modification ici doit être répercutée
# dans client-web-interface/nginx.conf et script.js (test de cohérence
# dans tests/test_timeouts.py).
REQUEST_BUDGET_SECONDS = 60.0

# Délais unitaires. Le pire cas théorique de la boucle d'outils
# (MAX_TOOL_ROUNDS tours) reste borné par REQUEST_BUDGET_SECONDS, qui
# enveloppe la totalité de ask_agent.
MCP_TIMEOUT_SECONDS = 8.0
LLM_TIMEOUT_SECONDS = 30.0
MAX_TOOL_ROUNDS = 4

# Le client web affiche la réponse avec textContent, sans parseur
# Markdown : tout balisage arriverait tel quel à l'écran ("**Prix** :
# 12 €"). On impose donc du texte brut plutôt que d'ajouter un rendu
# Markdown côté navigateur.
SYSTEM_PROMPT = (
    "Tu es l'assistant inventaire de HBNtory. Réponds en français et "
    "uniquement à partir des informations retournées par les outils MCP. "
    "Utilise le Product MCP pour identifier les produits et le Stock MCP "
    "pour connaître leur disponibilité. N'invente jamais un prix, un "
    "produit, une quantité ou une succursale. Si les données sont "
    "insuffisantes ou un service indisponible, dis-le clairement.\n"
    "Si l'utilisateur demande les produits d'une ville ou d'une "
    "succursale, le lieu n'est PAS une recherche de produit. Appelle "
    "dans le MÊME tour stock_get_stock_by_branch_name avec le lieu et "
    "products_list_products avec query vide et limit 100. Ces deux outils "
    "suffisent : n'appelle ensuite ni stock_find_branches, ni "
    "stock_get_stock_by_branch. Associe les product_id du stock aux noms "
    "du catalogue, puis réponds directement. Dans la réponse, liste "
    "UNIQUEMENT les produits présents dans le résultat de "
    "stock_get_stock_by_branch_name. Le catalogue sert seulement à "
    "retrouver leurs noms : un produit présent uniquement dans le "
    "catalogue n'est pas disponible dans cette succursale et ne doit "
    "jamais être affiché avec une quantité non spécifiée. Ne passe jamais "
    "un nom de ville dans query de products_list_products.\n"
    "Dans les autres cas, quand plusieurs outils peuvent être appelés "
    "indépendamment, appelle-les ensemble pour limiter les échanges.\n"
    "Réponds en TEXTE BRUT, jamais en Markdown : pas de titres avec #, "
    "pas de gras avec **, pas de tableaux, pas de blocs de code, pas de "
    "backticks. Fais des phrases courtes. Pour présenter plusieurs "
    "résultats, écris une phrase de résumé, une ligne vide, puis exactement "
    "une ligne par résultat au format « • Nom — N unité » ou "
    "« • Nom — N unités ». La puce typographique • fait partie du texte "
    "brut : n'utilise ni tiret ni astérisque comme puce Markdown."
)


class AgentServiceError(Exception):
    """Erreur contrôlée empêchant l'agent de produire une réponse fiable."""


class AgentTimeoutError(AgentServiceError):
    """Le budget global alloué à une question a été dépassé."""


class AgentRateLimitError(AgentServiceError):
    """Le fournisseur IA refuse temporairement de nouvelles requêtes."""

    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _retry_after_seconds(exc: RateLimitError) -> int | None:
    """Lit le délai conseillé par Groq sans exposer le corps de l'erreur."""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    raw_value = response.headers.get("retry-after")
    try:
        return max(1, int(float(raw_value)))
    except (TypeError, ValueError):
        return None


def build_mcp_client() -> Client:
    """Construit un client unique exposant les outils des deux MCP."""
    config = {
        "mcpServers": {
            "products": {
                "transport": "http",
                "url": PRODUCT_MCP_URL,
            },
            "stock": {
                "transport": "http",
                "url": STOCK_MCP_URL,
            },
        }
    }
    return Client(config)


def build_llm_client() -> AsyncOpenAI:
    """Construit le client Groq compatible avec l'API OpenAI."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise AgentServiceError(
            "La clé GROQ_API_KEY n'est pas configurée."
        )

    return AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=LLM_TIMEOUT_SECONDS,
        # Un 429 peut demander d'attendre près d'une minute. Les relances
        # automatiques du SDK immobiliseraient la requête jusqu'au timeout
        # tout en masquant la vraie cause au client.
        max_retries=0,
    )


def _to_openai_tools(mcp_tools: list[Any]) -> list[dict]:
    """Convertit les descriptions MCP au format d'outil OpenAI."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in mcp_tools
    ]


def _assistant_message(message: Any) -> dict:
    """Sérialise une réponse assistant au format standard OpenAI."""
    payload: dict[str, Any] = {
        "role": "assistant",
        "content": message.content,
    }
    if message.tool_calls:
        tool_calls = []
        for call in message.tool_calls:
            serialized_call = {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            tool_calls.append(serialized_call)
        payload["tool_calls"] = tool_calls
    return payload


def _parse_tool_arguments(raw_arguments: str) -> dict:
    """Valide que les arguments choisis par le LLM sont un objet JSON."""
    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as exc:
        raise AgentServiceError(
            "Le fournisseur IA a généré des arguments d'outil invalides."
        ) from exc

    if not isinstance(arguments, dict):
        raise AgentServiceError(
            "Le fournisseur IA a généré des arguments d'outil invalides."
        )
    return arguments


def _millisecondes(depuis: float) -> float:
    """Temps écoulé depuis un repère `time.monotonic()`."""
    return (time.monotonic() - depuis) * 1000


def _echec_signale(resultat: Any) -> str | None:
    """Repère un outil qui a répondu, mais pour signaler un problème.

    Les outils MCP du projet ne lèvent pas d'exception : ils renvoient
    `{"success": false, "error": "..."}`. Sans cette lecture, une base
    de données injoignable serait tracée comme un appel réussi.

    Le message d'erreur lui-même n'est jamais repris : c'est du contenu
    renvoyé par l'outil, dont on ne maîtrise pas ce qu'il transporte
    (chaîne de connexion, extrait de requête). Le journal se contente
    de constater l'échec ; le détail reste à la trace de l'exception
    ou aux journaux du serveur MCP concerné.
    """
    if isinstance(resultat, dict) and resultat.get("success") is False:
        return "erreur signalée par l'outil"
    return None


def _log_outil(question_id: str, nom: str, depuis: float,
               echec: str | None) -> None:
    """Trace un appel d'outil MCP : lequel, son issue, sa durée.

    `echec` vaut None quand l'outil a répondu normalement, sinon il
    donne une raison générique : le type de l'exception levée, ou le
    simple constat qu'un outil a signalé une erreur. Ni les arguments
    ni le contenu renvoyé ne sont journalisés : ils reprennent la
    question de l'utilisateur ou des pans entiers du catalogue. Le nom
    de l'outil suffit d'ailleurs à savoir quel serveur MCP a répondu,
    puisqu'il en porte le préfixe (`products_...`, `stock_...`).
    """
    duree = _millisecondes(depuis)
    if echec is None:
        logger.info("[%s] outil %s : succès en %.0f ms",
                    question_id, nom, duree)
    else:
        logger.warning("[%s] outil %s : échec en %.0f ms (%s)",
                       question_id, nom, duree, echec)


async def _run_agent(question: str, mcp_client: Client,
                     llm_client: AsyncOpenAI, question_id: str) -> str:
    """Exécute la boucle contrôlée LLM → outils MCP → réponse."""
    mcp_tools = await asyncio.wait_for(
        mcp_client.list_tools(),
        timeout=MCP_TIMEOUT_SECONDS,
    )
    openai_tools = _to_openai_tools(mcp_tools)
    if not openai_tools:
        raise AgentServiceError("Aucun outil MCP n'est disponible.")

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    tool_was_called = False
    model_candidates = list(dict.fromkeys(
        (AI_MODEL, *AI_FALLBACK_MODELS)
    ))
    active_model_index = 0

    async def request_completion(model: str):
        return await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=openai_tools,
                tool_choice=(
                    "auto" if tool_was_called else "required"
                ),
                temperature=0,
                max_tokens=1200,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )

    for _ in range(MAX_TOOL_ROUNDS):
        while True:
            active_model = model_candidates[active_model_index]
            try:
                completion = await request_completion(active_model)
                break
            except RateLimitError:
                if active_model_index + 1 >= len(model_candidates):
                    raise
                next_model = model_candidates[active_model_index + 1]
                logger.warning(
                    "[%s] modèle %s limité : bascule vers %s",
                    question_id,
                    active_model,
                    next_model,
                )
                active_model_index += 1
        message = completion.choices[0].message
        messages.append(_assistant_message(message))

        if not message.tool_calls:
            if not tool_was_called:
                raise AgentServiceError(
                    "Le fournisseur IA n'a utilisé aucun outil."
                )
            answer = (message.content or "").strip()
            if not answer:
                raise AgentServiceError(
                    "Le fournisseur IA a retourné une réponse vide."
                )
            return answer

        tool_was_called = True
        for tool_call in message.tool_calls:
            arguments = _parse_tool_arguments(
                tool_call.function.arguments
            )
            depuis = time.monotonic()
            try:
                result = await mcp_client.call_tool(
                    tool_call.function.name,
                    arguments,
                    timeout=MCP_TIMEOUT_SECONDS,
                )
                tool_content = result.data
            except Exception as exc:
                echec = type(exc).__name__
                tool_content = {
                    "success": False,
                    "error": "Le service de données est indisponible.",
                }
            else:
                echec = _echec_signale(tool_content)
            _log_outil(question_id, tool_call.function.name, depuis, echec)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(
                    tool_content,
                    ensure_ascii=False,
                    default=str,
                ),
            })

    raise AgentServiceError(
        "Le nombre maximal d'appels aux outils a été atteint."
    )


async def _ask_agent(question: str, question_id: str) -> str:
    """Ouvre les clients, délègue la boucle, puis referme tout."""
    try:
        llm_client = build_llm_client()
        try:
            async with build_mcp_client() as mcp_client:
                return await _run_agent(
                    question,
                    mcp_client,
                    llm_client,
                    question_id,
                )
        finally:
            await llm_client.close()
    except AgentServiceError:
        raise
    except RateLimitError as exc:
        raise AgentRateLimitError(
            "La limite temporaire du service IA est atteinte.",
            retry_after_seconds=_retry_after_seconds(exc),
        ) from exc
    except (asyncio.TimeoutError, TimeoutError) as exc:
        raise AgentServiceError(
            "Un service externe n'a pas répondu à temps."
        ) from exc
    except Exception as exc:
        raise AgentServiceError(
            "Le service d'assistance est temporairement indisponible."
        ) from exc


async def ask_agent(question: str) -> str:
    """Répond à une question sans accès direct à l'API ni à PostgreSQL.

    L'ensemble du traitement est borné par REQUEST_BUDGET_SECONDS : même
    si le LLM enchaîne les appels d'outils, une question ne peut pas
    durer plusieurs minutes.

    Chaque question reçoit un identifiant court, rappelé au début de
    toutes les lignes de journal qu'elle produit : deux questions
    traitées en même temps restent ainsi distinguables dans
    `docker compose logs ai-service`.
    """
    question_id = uuid4().hex[:8]
    depuis = time.monotonic()
    logger.info("[%s] question reçue (%d caractères)",
                question_id, len(question))
    try:
        answer = await asyncio.wait_for(
            _ask_agent(question, question_id),
            timeout=REQUEST_BUDGET_SECONDS,
        )
    except (asyncio.TimeoutError, TimeoutError) as exc:
        logger.warning("[%s] abandon après %.0f ms : budget de %.0f s "
                       "dépassé", question_id, _millisecondes(depuis),
                       REQUEST_BUDGET_SECONDS)
        raise AgentTimeoutError(
            "Le service d'assistance a mis trop de temps à répondre. "
            "Reformulez une question plus simple."
        ) from exc
    except AgentServiceError as exc:
        logger.warning("[%s] échec après %.0f ms (%s)",
                       question_id, _millisecondes(depuis), exc)
        raise
    logger.info("[%s] réponse produite en %.0f ms (%d caractères)",
                question_id, _millisecondes(depuis), len(answer))
    return answer
