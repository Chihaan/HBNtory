"""Tests unitaires de services/products.py (API externe mockée)."""

import pytest
import requests

import services.products as products
from services.products import product_exists, list_products
from services.errors import ProductApiUnavailable


class FakeResponse:
    """Fausse réponse HTTP contrôlable."""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _patch_get(monkeypatch, response=None, exc=None):
    def fake_get(url, timeout=None):
        if exc is not None:
            raise exc
        return response
    monkeypatch.setattr(products.requests, "get", fake_get)


def test_list_products_ok(monkeypatch):
    payload = {"results": [{"id": 1, "name": "Widget"}]}
    _patch_get(monkeypatch, FakeResponse(200, payload))
    assert list_products() == [{"id": 1, "name": "Widget"}]


def test_list_products_remplace_la_description_anglaise(monkeypatch):
    product = {
        "id": 1,
        "sku": "HB-LAP-1001",
        "name": "Holberton Student Laptop 14",
        "description": "Training catalog item.",
    }
    _patch_get(monkeypatch, FakeResponse(200, {"results": [product]}))

    localized = list_products()[0]

    assert localized["description"].startswith(
        "Ordinateur portable 14 pouces"
    )
    assert product["description"] == "Training catalog item."


def test_list_products_erreur_http(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(500))
    with pytest.raises(ProductApiUnavailable):
        list_products()


def test_list_products_injoignable(monkeypatch):
    _patch_get(monkeypatch, exc=requests.ConnectionError())
    with pytest.raises(ProductApiUnavailable):
        list_products()


def test_product_exists_vrai(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(200))
    assert product_exists(1) is True


def test_product_exists_faux_sur_404(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(404))
    assert product_exists(999) is False


def test_product_exists_erreur_serveur(monkeypatch):
    _patch_get(monkeypatch, FakeResponse(500))
    with pytest.raises(ProductApiUnavailable):
        product_exists(1)


def test_product_exists_injoignable(monkeypatch):
    _patch_get(monkeypatch, exc=requests.Timeout())
    with pytest.raises(ProductApiUnavailable):
        product_exists(1)
