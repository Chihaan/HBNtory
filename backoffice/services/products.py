"""Adaptateur vers l'API produits externe."""

import json
import os
from functools import lru_cache
from pathlib import Path

import requests

from services.errors import ProductApiUnavailable


BASE_URL = os.environ["PRODUCTS_API_URL"]
TIMEOUT = 3
DEFAULT_DESCRIPTIONS_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "product_descriptions_fr.json"
)
DESCRIPTIONS_PATH = Path(
    os.environ.get("PRODUCT_DESCRIPTIONS_PATH", DEFAULT_DESCRIPTIONS_PATH)
)


@lru_cache(maxsize=1)
def _french_descriptions():
    """Charge le catalogue local sans rendre l'API externe obligatoire."""
    try:
        with DESCRIPTIONS_PATH.open(encoding="utf-8") as source:
            descriptions = json.load(source)
    except (OSError, json.JSONDecodeError):
        return {}
    return descriptions if isinstance(descriptions, dict) else {}


def _localize_product(product):
    """Remplace uniquement la description lorsqu'une traduction existe."""
    if not isinstance(product, dict):
        return product
    description = _french_descriptions().get(product.get("sku"))
    if not description:
        return product
    return {**product, "description": description}


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
    return [
        _localize_product(product)
        for product in response.json()["results"]
    ]
