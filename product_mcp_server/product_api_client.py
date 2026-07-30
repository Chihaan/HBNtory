import json
import os
from functools import lru_cache
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PRODUCT_API_URL = os.getenv("PRODUCT_API_URL", "http://localhost:5001")
DEFAULT_DESCRIPTIONS_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "product_descriptions_fr.json"
)
DESCRIPTIONS_PATH = Path(
    os.environ.get("PRODUCT_DESCRIPTIONS_PATH", DEFAULT_DESCRIPTIONS_PATH)
)

# L'API accepte ?simulate_delay_ms jusqu'a 3000 ms (voir son README).
# La marge evite de couper une reponse volontairement lente, tout en gardant
# une duree finie pour ne jamais bloquer le serveur MCP.
REQUEST_TIMEOUT = 5


@lru_cache(maxsize=1)
def _french_descriptions():
    """Charge les descriptions locales sans modifier l'API fournie."""
    try:
        with DESCRIPTIONS_PATH.open(encoding="utf-8") as source:
            descriptions = json.load(source)
    except (OSError, json.JSONDecodeError):
        return {}
    return descriptions if isinstance(descriptions, dict) else {}


def _localize_product(product):
    """Remplace la description du produit si une traduction est disponible."""
    if not isinstance(product, dict):
        return product
    description = _french_descriptions().get(product.get("sku"))
    if not description:
        return product
    return {**product, "description": description}


class ProductAPIError(Exception):
    """Exception levee quand la communication avec la Product API echoue
    (connexion, timeout, statut HTTP inattendu ou JSON invalide).

    Transporte un message clair, reutilisable par le serveur MCP pour
    construire une reponse d'erreur explicite pour l'agent IA.
    """
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ProductNotFoundError(ProductAPIError):
    """Erreur specifique lorsqu'un produit n'existe pas (HTTP 404)."""
    pass


def _extract_error_message(response, fallback: str) -> str:
    """Extrait le message d'erreur JSON ou retourne le texte de secours."""
    try:
        body = response.json()
        if isinstance(body, dict) and "message" in body:
            return body["message"]
    except ValueError:
        pass
    return fallback


def _do_get(path: str, params: dict | None = None):
    """Effectue un GET et centralise la gestion des erreurs reseau."""
    try:
        return requests.get(
            f"{PRODUCT_API_URL}{path}",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        raise ProductAPIError(
            "Impossible de se connecter a la Product API a l'adresse "
            f"{PRODUCT_API_URL}. "
            "Verifiez que le service est demarre et accessible."
        )
    except requests.exceptions.Timeout:
        raise ProductAPIError(
            "La Product API n'a pas repondu dans le delai imparti "
            f"({REQUEST_TIMEOUT}s)."
        )
    except requests.exceptions.RequestException as e:
        raise ProductAPIError(
            "Erreur inattendue lors de l'appel a la Product API: "
            f"{e}"
        )


def fetch_products(
    q: str | None = None,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Appelle GET /api/v1/products sur la Product API.

    Retourne le dictionnaire brut de pagination fourni par l'API.
    Leve ProductAPIError si la requete echoue.
    """
    params = {"limit": limit, "offset": offset}
    if q:
        params["q"] = q
    if category:
        params["category"] = category

    response = _do_get("/api/v1/products", params=params)

    if response.status_code != 200:
        message = _extract_error_message(
            response,
            "La Product API a retourne un statut inattendu: "
            f"{response.status_code}",
        )
        raise ProductAPIError(message, status_code=response.status_code)

    try:
        payload = response.json()
    except ValueError:
        raise ProductAPIError(
            "La Product API a retourne une reponse qui n'est pas "
            "du JSON valide."
        )
    payload["results"] = [
        _localize_product(product)
        for product in payload.get("results", [])
    ]
    return payload


def fetch_product_by_id(product_id: str) -> dict:
    """Appelle GET /api/v1/products/{id} sur la Product API.

    Note: cet endpoint de la Product API accepte techniquement aussi bien
    l'id numerique que le SKU comme identifiant. Notre systeme n'utilise
    volontairement que l'id numerique (product_id), car c'est cet
    identifiant qui est aussi stocke dans la table stock de notre base de
    donnees pour associer une quantite a un produit.

    Retourne le dictionnaire produit.
    Leve ProductNotFoundError si le produit n'existe pas (404).
    Leve ProductAPIError pour toute autre erreur de communication.
    """
    response = _do_get(f"/api/v1/products/{product_id}")

    if response.status_code == 404:
        message = _extract_error_message(
            response,
            f"Aucun produit trouve avec l'identifiant '{product_id}'.",
        )
        raise ProductNotFoundError(message)

    if response.status_code != 200:
        message = _extract_error_message(
            response,
            "La Product API a retourne un statut inattendu: "
            f"{response.status_code}",
        )
        raise ProductAPIError(message, status_code=response.status_code)

    try:
        product = response.json()
    except ValueError:
        raise ProductAPIError(
            "La Product API a retourne une reponse qui n'est pas "
            "du JSON valide."
        )
    return _localize_product(product)
