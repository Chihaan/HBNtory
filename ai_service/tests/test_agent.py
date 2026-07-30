"""Tests de l'orchestration LLM vers les outils MCP."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

import agent


def test_client_llm_utilise_la_configuration_groq(monkeypatch):
    parametres_recus = {}

    def faux_client(**parametres):
        parametres_recus.update(parametres)
        return SimpleNamespace()

    monkeypatch.setenv("GROQ_API_KEY", "cle-groq-de-test")
    monkeypatch.setattr(agent, "AsyncOpenAI", faux_client)

    agent.build_llm_client()

    assert parametres_recus["api_key"] == "cle-groq-de-test"
    assert parametres_recus["base_url"] == (
        "https://api.groq.com/openai/v1"
    )
    assert parametres_recus["timeout"] == agent.LLM_TIMEOUT_SECONDS
    assert parametres_recus["max_retries"] == 0


def test_client_llm_refuse_une_cle_groq_absente(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(agent.AgentServiceError, match="GROQ_API_KEY"):
        agent.build_llm_client()


class FakeMCP:
    """Double minimal du client FastMCP."""

    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return [
            SimpleNamespace(
                name="products_list_products",
                description="Recherche des produits.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
            )
        ]

    async def call_tool(self, name, arguments, timeout):
        self.calls.append((name, arguments, timeout))
        return SimpleNamespace(data={
            "success": True,
            "products": [{"id": 1, "name": "Laptop"}],
        })


class FakeCompletions:
    """Retourne d'abord un appel d'outil, puis une réponse finale."""

    def __init__(self):
        self.calls = []
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(
                name="products_list_products",
                arguments='{"query": "laptop"}',
            ),
            # Métadonnée non standard que certains fournisseurs ajoutent :
            # elle ne doit pas être renvoyée à Groq.
            extra_content={
                "google": {
                    "thought_signature": "opaque-signature",
                },
            },
        )
        self.messages = [
            SimpleNamespace(content=None, tool_calls=[tool_call]),
            SimpleNamespace(
                content="Le Laptop est disponible.",
                tool_calls=None,
            ),
        ]

    async def create(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        message = self.messages.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )


class FallbackCompletions(FakeCompletions):
    """Le modèle principal est limité, le modèle de secours répond."""

    async def create(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        if kwargs["model"] == "modele-principal":
            response = httpx.Response(
                429,
                request=httpx.Request("POST", "https://api.groq.test"),
            )
            raise RateLimitError(
                "quota atteint",
                response=response,
                body={"code": "rate_limit_exceeded"},
            )
        message = self.messages.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )


class MultipleFallbackCompletions(FallbackCompletions):
    """Deux modèles sont limités avant que le troisième ne réponde."""

    async def create(self, **kwargs):
        if kwargs["model"] == "premier-secours":
            self.calls.append(deepcopy(kwargs))
            response = httpx.Response(
                429,
                request=httpx.Request("POST", "https://api.groq.test"),
            )
            raise RateLimitError(
                "quota atteint",
                response=response,
                body={"code": "rate_limit_exceeded"},
            )
        return await super().create(**kwargs)


def test_agent_execute_un_outil_mcp_puis_repond():
    mcp_client = FakeMCP()
    completions = FakeCompletions()
    llm_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    answer = asyncio.run(
        agent._run_agent(
            "Je cherche un laptop.", mcp_client, llm_client, "test1234"
        )
    )

    assert answer == "Le Laptop est disponible."
    assert mcp_client.calls == [(
        "products_list_products",
        {"query": "laptop"},
        agent.MCP_TIMEOUT_SECONDS,
    )]
    second_messages = completions.calls[1]["messages"]
    assert second_messages[-1]["role"] == "tool"
    assert '"success": true' in second_messages[-1]["content"]
    assistant_tool_call = second_messages[-2]["tool_calls"][0]
    assert "extra_content" not in assistant_tool_call
    assert completions.calls[0]["tool_choice"] == "required"
    assert completions.calls[1]["tool_choice"] == "auto"


def test_agent_bascule_sur_le_modele_de_secours(monkeypatch):
    mcp_client = FakeMCP()
    completions = FallbackCompletions()
    llm_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    monkeypatch.setattr(agent, "AI_MODEL", "modele-principal")
    monkeypatch.setattr(
        agent,
        "AI_FALLBACK_MODELS",
        ("modele-secours",),
    )

    answer = asyncio.run(
        agent._run_agent(
            "Je cherche un laptop.", mcp_client, llm_client, "test1234"
        )
    )

    assert answer == "Le Laptop est disponible."
    assert [call["model"] for call in completions.calls] == [
        "modele-principal",
        "modele-secours",
        "modele-secours",
    ]


def test_agent_parcourt_plusieurs_modeles_de_secours(monkeypatch):
    completions = MultipleFallbackCompletions()
    llm_client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    monkeypatch.setattr(agent, "AI_MODEL", "modele-principal")
    monkeypatch.setattr(
        agent,
        "AI_FALLBACK_MODELS",
        ("premier-secours", "second-secours"),
    )

    answer = asyncio.run(
        agent._run_agent(
            "Je cherche un laptop.",
            FakeMCP(),
            llm_client,
            "test1234",
        )
    )

    assert answer == "Le Laptop est disponible."
    assert [call["model"] for call in completions.calls] == [
        "modele-principal",
        "premier-secours",
        "second-secours",
        "second-secours",
    ]


@pytest.mark.parametrize("arguments", ["[1]", "{", "null"])
def test_arguments_outil_invalides_refuses(arguments):
    with pytest.raises(agent.AgentServiceError):
        agent._parse_tool_arguments(arguments)


def test_tout_outil_publie_par_un_mcp_est_expose_au_llm():
    """La découverte est dynamique : aucun outil n'est codé en dur.

    Un outil ajouté côté serveur MCP (ici `stock_find_branches`) est
    donc transmis au LLM sans modifier l'AI Service.
    """
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
    }
    outils = agent._to_openai_tools([
        SimpleNamespace(
            name="stock_find_branches",
            description="Retrouve une succursale par son nom.",
            inputSchema=schema,
        ),
    ])

    assert outils == [{
        "type": "function",
        "function": {
            "name": "stock_find_branches",
            "description": "Retrouve une succursale par son nom.",
            "parameters": schema,
        },
    }]


def test_le_prompt_systeme_interdit_le_markdown():
    """Le client web affiche la réponse telle quelle, via textContent.

    Sans parseur Markdown côté navigateur, un titre `#` ou un `**gras**`
    s'afficherait littéralement. L'interdiction doit donc rester dans le
    prompt tant que le CWI n'utilise pas innerHTML.
    """
    prompt = agent.SYSTEM_PROMPT

    assert "TEXTE BRUT" in prompt
    for interdit in ("titres avec #", "gras avec **", "tableaux",
                     "blocs de code", "backticks"):
        assert interdit in prompt
    assert "• Nom — N unité" in prompt
    assert "puce typographique •" in prompt


def test_le_prompt_distingue_un_lieu_d_un_produit():
    prompt = agent.SYSTEM_PROMPT

    assert "le lieu n'est PAS une recherche de produit" in prompt
    assert "stock_get_stock_by_branch_name" in prompt
    assert "dans le MÊME tour" in prompt
    assert "query vide et limit 100" in prompt
    assert "UNIQUEMENT les produits présents" in prompt
    assert "quantité non spécifiée" in prompt
