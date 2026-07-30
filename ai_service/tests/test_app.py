"""Tests HTTP de l'AI Service sans appel réseau."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app as app_module
from agent import AgentRateLimitError, AgentServiceError

client = TestClient(app_module.app)


class FakeProductMCP:
    """Double asynchrone du client MCP utilisé par les routes catalogue."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def call_tool(self, name, arguments, timeout):
        self.calls.append((name, arguments, timeout))
        return SimpleNamespace(data=self.responses.pop(0))


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_catalogue_produits_passe_par_le_product_mcp(monkeypatch):
    mcp = FakeProductMCP([{
        "success": True,
        "products": [{
            "id": 1,
            "sku": "HB-LAP-1001",
            "name": "Holberton Student Laptop 14",
        }],
    }])
    monkeypatch.setattr(app_module, "build_mcp_client", lambda: mcp)

    response = client.get("/products")

    assert response.status_code == 200
    assert response.json()["products"][0]["sku"] == "HB-LAP-1001"
    assert mcp.calls == [(
        "products_list_products",
        {"query": "", "limit": 100},
        app_module.MCP_TIMEOUT_SECONDS,
    )]


def test_detail_produit_passe_par_le_product_mcp(monkeypatch):
    mcp = FakeProductMCP([{
        "success": True,
        "product": {
            "id": 1,
            "sku": "HB-LAP-1001",
            "name": "Holberton Student Laptop 14",
            "description": "Un ordinateur de formation.",
        },
    }])
    monkeypatch.setattr(app_module, "build_mcp_client", lambda: mcp)

    response = client.get("/products/1")

    assert response.status_code == 200
    assert response.json()["product"]["description"] == (
        "Un ordinateur de formation."
    )
    assert mcp.calls[0][0:2] == (
        "products_get_product_details",
        {"product_id": 1},
    )


def test_detail_produit_inconnu_renvoie_404(monkeypatch):
    mcp = FakeProductMCP([{
        "success": False,
        "product": None,
    }])
    monkeypatch.setattr(app_module, "build_mcp_client", lambda: mcp)

    response = client.get("/products/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ce produit est introuvable."


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


def test_websocket_diffuse_etapes_fragments_et_fin(monkeypatch):
    async def fake_ask(question, on_event=None):
        assert question == "Quels produits à Fréjus ?"
        await on_event({
            "type": "status",
            "step": "stock",
            "state": "active",
            "message": "Consultation du stock…",
        })
        await on_event({"type": "chunk", "content": "Deux "})
        await on_event({"type": "chunk", "content": "produits."})
        return "Deux produits."

    monkeypatch.setattr(app_module, "ask_agent", fake_ask)

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({
            "type": "question",
            "request_id": "requete-1",
            "question": "  Quels produits à Fréjus ?  ",
        })
        events = [websocket.receive_json() for _ in range(4)]

    assert [event["type"] for event in events] == [
        "status",
        "chunk",
        "chunk",
        "done",
    ]
    assert all(
        event["request_id"] == "requete-1"
        for event in events
    )
    assert "".join(
        event.get("content", "")
        for event in events
    ) == "Deux produits."


def test_websocket_refuse_une_question_invalide():
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({
            "type": "question",
            "request_id": "requete-2",
            "question": "   ",
        })
        event = websocket.receive_json()

    assert event == {
        "type": "error",
        "request_id": "requete-2",
        "detail": "La question doit contenir entre 1 et 1000 caractères.",
    }
