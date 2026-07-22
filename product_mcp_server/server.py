#!/usr/bin/env python3
import os
import requests
from typing import Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# -----------------------------------------------------------------------------
# Configuration et variables d'environnement
# -----------------------------------------------------------------------------
API_URL = os.getenv("PRODUCT_API_URL", "http://localhost:5001")
API_PREFIX = os.getenv("PRODUCT_API_PREFIX", "/api/v1")
BASE_URL = f"{API_URL.rstrip('/')}{API_PREFIX}"
TIMEOUT_SECONDES = 5

mcp = FastMCP("product-mcp-server")


# -----------------------------------------------------------------------------
# Fonction d'aide centralisée pour les appels API
# -----------------------------------------------------------------------------
def _appeler_api(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Effectue la requête HTTP vers l'API externe et gère les erreurs réseau."""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDES)

        if response.status_code == 404:
            return {"error": "Élément introuvable (404)."}

        if response.status_code != 200:
            return {"error": f"Erreur de l'API backend : statut HTTP {response.status_code}"}

        return response.json()

    except requests.exceptions.Timeout:
        return {"error": "L'API produits est trop lente à répondre, réessaye."}
    except requests.exceptions.ConnectionError:
        return {"error": "L'API produits est actuellement indisponible (erreur de connexion)."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Erreur lors de la communication avec l'API : {str(e)}"}


# -----------------------------------------------------------------------------
# Outils MCP
# -----------------------------------------------------------------------------
@mcp.tool()
def list_products() -> dict:
    """
    Liste tous les produits du catalogue externe.
    Inclut les produits discontinués pour éviter les pannes sur les stocks existants.
    """
    params = {
        "include_discontinued": "true",
        "sort": "name",
        "limit": 100
    }
    resultat = _appeler_api("products", params=params)

    if "error" in resultat:
        return resultat

    return {"products": resultat.get("results", [])}


@mcp.tool()
def get_product(id_produit: str) -> dict:
    """
    Obtenir les détails complets d'un produit par son ID.
    Retourne un message d'erreur explicite si le produit n'existe pas.
    """
    resultat = _appeler_api(f"products/{id_produit}")

    if "error" in resultat and resultat.get("status") == 404:
        return {"error": f"Produit avec l'ID '{id_produit}' introuvable."}

    return resultat


# -----------------------------------------------------------------------------
# Démarrage du serveur
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="streamable-http")