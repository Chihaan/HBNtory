"""Contrats de configuration partagés par les services."""

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.exemple"
DESCRIPTIONS = ROOT / "data" / "product_descriptions_fr.json"
PRODUCTS = ROOT / "external" / "product-api" / "data" / "products.json"


def _example_variables():
    """Retourne les noms déclarés dans .env.exemple, sans les journaliser."""
    variables = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            variables[name] = value
    return variables


def test_env_exemple_configure_les_deux_consommateurs_produits():
    variables = _example_variables()

    assert variables["PRODUCT_API_URL"] == (
        "http://external-products-api:5000"
    )
    assert variables["PRODUCTS_API_URL"] == (
        "http://external-products-api:5000"
    )


def test_import_backoffice_depuis_les_noms_de_env_exemple():
    """Tous les noms existent, sans réutiliser ni afficher leurs valeurs."""
    environment = {
        name: "valeur-de-test"
        for name in _example_variables()
    }
    environment["PATH"] = os.environ.get("PATH", "")

    result = subprocess.run(
        [sys.executable, "-c", "import services.products"],
        cwd=ROOT / "backoffice",
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0


def test_catalogue_francais_couvre_tous_les_produits():
    """Chaque SKU fourni possède une description française dédiée."""
    descriptions = json.loads(DESCRIPTIONS.read_text(encoding="utf-8"))
    products = json.loads(PRODUCTS.read_text(encoding="utf-8"))["products"]

    assert set(descriptions) == {product["sku"] for product in products}
    assert len(descriptions) == 40
    assert all(description.strip() for description in descriptions.values())
