"""Tests automatisés des outils publics du Product MCP."""

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server
from product_api_client import ProductAPIError, ProductNotFoundError


def _appeler(nom_outil, arguments):
    """Appelle un outil comme le ferait l'agent, via le protocole MCP."""
    async def call_tool():
        async with Client(server.mcp) as client:
            return await client.call_tool(nom_outil, arguments)

    return asyncio.run(call_tool()).data


def test_serveur_expose_les_deux_outils():
    async def list_tools():
        async with Client(server.mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())

    assert {tool.name for tool in tools} == {
        "list_products",
        "get_product_details",
    }
    assert sum(len(tool.description or "") for tool in tools) < 500


def test_recherche_produit_passe_par_api_client(monkeypatch):
    def fake_fetch_products(q, limit):
        assert q == "laptop"
        assert limit == 5
        return {
            "count": 1,
            "results": [{"id": 1, "name": "Laptop"}],
        }

    monkeypatch.setattr(server, "fetch_products", fake_fetch_products)

    async def call_tool():
        async with Client(server.mcp) as client:
            return await client.call_tool(
                "list_products",
                {"query": "laptop", "limit": 5},
            )

    result = asyncio.run(call_tool())
    assert result.data == {
        "success": True,
        "count": 1,
        "products": [{"id": 1, "name": "Laptop"}],
        "error": None,
    }


def test_liste_du_catalogue_sans_filtre(monkeypatch):
    """Sans texte de recherche, on liste le catalogue au lieu de filtrer."""
    def fake_fetch_products(q, limit):
        assert q is None
        return {"count": 39, "results": [{"id": 4, "name": "Monitor"}]}

    monkeypatch.setattr(server, "fetch_products", fake_fetch_products)

    data = _appeler("list_products", {})

    assert data["success"] is True
    assert data["count"] == 39
    assert data["products"] == [{"id": 4, "name": "Monitor"}]


def test_liste_retourne_des_resumes_compacts(monkeypatch):
    """Le catalogue ne répète pas les descriptions dans chaque tour LLM."""
    def fake_fetch_products(q, limit):
        return {
            "count": 1,
            "results": [{
                "id": 4,
                "sku": "MON-004",
                "name": "Monitor",
                "brand": "Nexa",
                "category": "Displays",
                "unit_price": 199.0,
                "currency": "EUR",
                "discontinued": False,
                "description": "Description volontairement longue.",
                "tags": ["display", "office"],
                "supplier_name": "Fournisseur",
            }],
        }

    monkeypatch.setattr(server, "fetch_products", fake_fetch_products)

    data = _appeler("list_products", {})

    assert data["products"] == [{
        "id": 4,
        "sku": "MON-004",
        "name": "Monitor",
        "brand": "Nexa",
        "category": "Displays",
        "unit_price": 199.0,
        "currency": "EUR",
        "discontinued": False,
    }]


def test_details_produit_existant(monkeypatch):
    """L'id numerique est transmis a la Product API sous forme de chaine."""
    def fake_fetch_product_by_id(product_id):
        assert product_id == "1"
        return {"id": 1, "sku": "HB-LAP-1001", "unit_price": 799.0}

    monkeypatch.setattr(
        server, "fetch_product_by_id", fake_fetch_product_by_id
    )

    data = _appeler("get_product_details", {"product_id": 1})

    assert data == {
        "success": True,
        "product": {"id": 1, "sku": "HB-LAP-1001", "unit_price": 799.0},
        "error": None,
    }


def test_produit_absent_est_signale_sans_lever_d_exception(monkeypatch):
    """Un produit inexistant est une reponse normale, pas une panne MCP."""
    def fake_fetch_product_by_id(product_id):
        raise ProductNotFoundError("Product not found.")

    monkeypatch.setattr(
        server, "fetch_product_by_id", fake_fetch_product_by_id
    )

    data = _appeler("get_product_details", {"product_id": 9999})

    assert data == {
        "success": False,
        "product": None,
        "error": "Product not found.",
    }


def test_api_injoignable_sur_les_details(monkeypatch):
    """Une panne reseau remonte a l'agent comme un message, pas un crash."""
    message = (
        "Impossible de se connecter a la Product API a l'adresse "
        "http://localhost:5001. Verifiez que le service est demarre "
        "et accessible."
    )

    def fake_fetch_product_by_id(product_id):
        raise ProductAPIError(message)

    monkeypatch.setattr(
        server, "fetch_product_by_id", fake_fetch_product_by_id
    )

    data = _appeler("get_product_details", {"product_id": 1})

    assert data["success"] is False
    assert data["product"] is None
    assert data["error"] == message


def test_un_sku_a_la_place_d_un_id_est_refuse_avant_tout_appel(monkeypatch):
    """L'outil n'accepte que l'id numerique, jamais le SKU.

    Les produits retournes exposent aussi un champ "sku" : l'agent peut
    confondre les deux. La validation d'entree de FastMCP arrete l'appel
    avant la Product API, avec un message explicite.
    """
    def jamais_appele(product_id):
        raise AssertionError("la Product API ne doit pas etre appelee")

    monkeypatch.setattr(server, "fetch_product_by_id", jamais_appele)

    with pytest.raises(ToolError, match="valid integer"):
        _appeler("get_product_details", {"product_id": "HB-LAP-1001"})


def test_api_injoignable_sur_la_liste(monkeypatch):
    """Meme panne cote recherche : liste vide et message exploitable."""
    def fake_fetch_products(q, limit):
        raise ProductAPIError("Forced simulation error.", status_code=503)

    monkeypatch.setattr(server, "fetch_products", fake_fetch_products)

    data = _appeler("list_products", {"query": "laptop"})

    assert data == {
        "success": False,
        "count": 0,
        "products": [],
        "error": "Forced simulation error.",
    }
