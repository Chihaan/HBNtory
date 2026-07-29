import os
import requests
from dotenv import load_dotenv

load_dotenv()

PRODUCT_API_URL = os.getenv("PRODUCT_API_URL", "http://localhost:5001")

# La Product API accepte ?simulate_delay_ms jusqu'a 3000ms (voir README du repo).
# On met un timeout un peu au-dessus pour ne pas couper une reponse volontairement lente,
# tout en restant fini pour ne jamais bloquer le serveur MCP indefiniment.
REQUEST_TIMEOUT = 5


class ProductAPIError(Exception):
    """Exception levee quand la communication avec la Product API echoue
    (connexion, timeout, statut HTTP inattendu, JSON invalide, panne simulee...).

    Transporte un message clair, reutilisable par le serveur MCP pour
    construire une reponse d'erreur explicite pour l'agent IA.
    """
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ProductNotFoundError(ProductAPIError):
    """Exception specifique quand un produit demande n'existe pas (HTTP 404)."""
    pass


def _extract_error_message(response, fallback: str) -> str:
    """La Product API renvoie les erreurs au format {"error": "...", "message": "..."}.
    On essaie de recuperer ce message pour donner un retour precis; sinon on retombe
    sur un message generique."""
    try:
        body = response.json()
        if isinstance(body, dict) and "message" in body:
            return body["message"]
    except ValueError:
        pass
    return fallback


def _do_get(path: str, params: dict | None = None):
    """Effectue un GET vers la Product API et centralise la gestion des erreurs reseau
    (connexion refusee, timeout, exception requests generique)."""
    try:
        return requests.get(f"{PRODUCT_API_URL}{path}", params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.ConnectionError:
        raise ProductAPIError(
            f"Impossible de se connecter a la Product API a l'adresse {PRODUCT_API_URL}. "
            "Verifiez que le service est demarre et accessible."
        )
    except requests.exceptions.Timeout:
        raise ProductAPIError(
            f"La Product API n'a pas repondu dans le delai imparti ({REQUEST_TIMEOUT}s)."
        )
    except requests.exceptions.RequestException as e:
        raise ProductAPIError(f"Erreur inattendue lors de l'appel a la Product API: {e}")


def fetch_products(
    q: str | None = None,
    category: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Appelle GET /api/v1/products sur la Product API.

    Retourne le dictionnaire brut de pagination: {"count", "limit", "offset", "results"}.
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
            response, f"La Product API a retourne un statut inattendu: {response.status_code}"
        )
        raise ProductAPIError(message, status_code=response.status_code)

    try:
        return response.json()
    except ValueError:
        raise ProductAPIError("La Product API a retourne une reponse qui n'est pas du JSON valide.")


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
        message = _extract_error_message(response, f"Aucun produit trouve avec l'identifiant '{product_id}'.")
        raise ProductNotFoundError(message)

    if response.status_code != 200:
        message = _extract_error_message(
            response, f"La Product API a retourne un statut inattendu: {response.status_code}"
        )
        raise ProductAPIError(message, status_code=response.status_code)

    try:
        return response.json()
    except ValueError:
        raise ProductAPIError("La Product API a retourne une reponse qui n'est pas du JSON valide.")
