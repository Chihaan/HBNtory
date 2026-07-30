"""Tests HTTP de l'AI Service sans appel réseau."""

from fastapi.testclient import TestClient

import app as app_module
from agent import AgentRateLimitError, AgentServiceError

client = TestClient(app_module.app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_question_valide(monkeypatch):
    async def fake_ask(question):
        assert question == "Où est le produit 1 ?"
        return "Il est disponible à Fréjus."

    monkeypatch.setattr(app_module, "ask_agent", fake_ask)
    response = client.post(
        "/ask",
        json={"question": "  Où est le produit 1 ?  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Il est disponible à Fréjus.",
    }


def test_question_vide_refusee():
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code == 422


def test_question_trop_longue_refusee():
    response = client.post("/ask", json={"question": "a" * 1001})

    assert response.status_code == 422


def test_erreur_technique_masquee(monkeypatch):
    async def failing_ask(question):
        raise AgentServiceError("secret technique")

    monkeypatch.setattr(app_module, "ask_agent", failing_ask)
    response = client.post("/ask", json={"question": "Un produit ?"})

    assert response.status_code == 503
    assert "secret technique" not in response.text


def test_limite_fournisseur_expliquee(monkeypatch):
    async def rate_limited_ask(question):
        raise AgentRateLimitError("detail fournisseur")

    monkeypatch.setattr(app_module, "ask_agent", rate_limited_ask)
    response = client.post("/ask", json={"question": "Un produit ?"})

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "La limite temporaire du service IA est atteinte. "
        "Réessayez dans une minute."
    )
    assert "detail fournisseur" not in response.text


def test_limite_quotidienne_indique_le_delai_reel(monkeypatch):
    async def rate_limited_ask(question):
        raise AgentRateLimitError(
            "detail fournisseur",
            retry_after_seconds=1432,
        )

    monkeypatch.setattr(app_module, "ask_agent", rate_limited_ask)
    response = client.post("/ask", json={"question": "Un produit ?"})

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "La limite temporaire du service IA est atteinte. "
        "Réessayez dans environ 24 minutes."
    )
