"""Tests de l'enrichissement local du catalogue fourni."""

import product_api_client as client


class FakeResponse:
    """Réponse HTTP minimale utilisée sans contacter l'API."""

    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_fetch_products_applique_la_description_francaise(monkeypatch):
    product = {
        "id": 40,
        "sku": "HB-LGT-1801",
        "description": "Training catalog item.",
    }
    response = FakeResponse({"count": 1, "results": [product]})
    monkeypatch.setattr(client, "_do_get", lambda path, params: response)

    result = client.fetch_products()

    assert result["results"][0]["description"].startswith(
        "Lampe de bureau LED"
    )
    assert product["description"] == "Training catalog item."


def test_fetch_product_by_id_applique_la_description_francaise(monkeypatch):
    product = {
        "id": 35,
        "sku": "HB-PRN-1501",
        "description": "Training catalog item.",
    }
    monkeypatch.setattr(
        client,
        "_do_get",
        lambda path: FakeResponse(product),
    )

    result = client.fetch_product_by_id("35")

    assert result["description"].startswith("Imprimante thermique compacte")
    assert product["description"] == "Training catalog item."


def test_produit_inconnu_conserve_sa_description(monkeypatch):
    product = {
        "id": 999,
        "sku": "INCONNU",
        "description": "Description reçue.",
    }
    monkeypatch.setattr(
        client,
        "_do_get",
        lambda path: FakeResponse(product),
    )

    assert client.fetch_product_by_id("999") == product
