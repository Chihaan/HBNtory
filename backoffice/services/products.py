"""Adaptateur vers l'API produits externe."""

import os

import requests

from services.errors import ProductApiUnavailable


BASE_URL = os.environ["PRODUCTS_API_URL"]
TIMEOUT = 3


def product_exists(product_id):
    """Indique si l'API produits externe connaît ce product_id."""
    url = f"{BASE_URL}/api/v1/products/{product_id}"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 404:
            return False
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProductApiUnavailable(
            f"API produits injoignable pour le produit {product_id}."
        ) from exc
    return True


def list_products():
    """Retourne tous les produits de l'API (discontinued inclus)."""
    url = f"{BASE_URL}/api/v1/products?limit=100&include_discontinued=true"
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProductApiUnavailable(
            "API produits injoignable pour la liste de produits."
        ) from exc
    return response.json()["results"]
