from fastmcp import FastMCP

from product_api_client import (
    fetch_products,
    fetch_product_by_id,
    ProductAPIError,
    ProductNotFoundError,
)

mcp = FastMCP("product-mcp-server")

LIST_PRODUCTS_DESCRIPTION = (
    "Recherche des produits par nom, description ou tag. Une query vide "
    "liste le catalogue. Retourne des résumés avec id, nom, catégorie, "
    "marque, prix et SKU. Utiliser l'id avec les outils de stock."
)
PRODUCT_DETAILS_DESCRIPTION = (
    "Retourne les informations complètes d'un produit déjà identifié par "
    "son product_id numérique."
)

PRODUCT_SUMMARY_FIELDS = (
    "id",
    "sku",
    "name",
    "brand",
    "category",
    "unit_price",
    "currency",
    "discontinued",
)


def _product_summary(product: dict) -> dict:
    """Conserve les champs utiles pour identifier un produit dans une liste."""
    return {
        field: product[field]
        for field in PRODUCT_SUMMARY_FIELDS
        if field in product
    }


@mcp.tool(description=LIST_PRODUCTS_DESCRIPTION)
def list_products(query: str = "", limit: int = 20) -> dict:
    """Recherche des produits a partir d'un texte libre, ou liste le catalogue.

    Utiliser cet outil lorsque l'utilisateur demande quels produits
    existent, fournit un nom, une description partielle ou un tag, ou a
    besoin de retrouver l'identifiant d'un produit avant de demander ses
    details (`get_product_details`) ou de verifier son stock. Pour
    recuperer les details d'un produit deja identifie par son id, utiliser
    plutot `get_product_details`.

    Args:
        query: Texte a rechercher dans le nom, la description et les tags
            des produits. Laisser vide pour lister le catalogue sans filtre.
        limit: Nombre maximum de produits a retourner (defaut 20, max 100).

    Returns:
        Un dictionnaire contenant:
        - success (bool): indique si l'appel a reussi.
        - count (int): nombre total de produits correspondants cote
          fournisseur.
        - products (list): résumés des produits pour cette page, si succès,
          avec id, sku, name, brand, category, unit_price, currency et
          discontinued. Le détail complet reste accessible avec
          get_product_details. Le champ "id" est l'identifiant à employer
          pour les outils de stock, jamais le champ "sku".
        - error (str ou null): message d'erreur clair si l'appel a echoue.
    """
    try:
        payload = fetch_products(q=query or None, limit=limit)
        products = [
            _product_summary(product)
            for product in payload.get("results", [])
        ]
        return {
            "success": True,
            "count": payload.get("count", len(products)),
            "products": products,
            "error": None,
        }
    except ProductAPIError as e:
        return {
            "success": False,
            "count": 0,
            "products": [],
            "error": e.message,
        }


@mcp.tool(description=PRODUCT_DETAILS_DESCRIPTION)
def get_product_details(product_id: int) -> dict:
    """Recupere le detail complet d'un produit deja identifie par son id.

    Utiliser cet outil lorsque l'utilisateur demande des details sur un
    produit precis dont l'id est deja connu (obtenu via `list_products`).
    Pour chercher un produit a partir d'un nom, d'une description ou d'un
    tag, utiliser plutot `list_products`.

    Args:
        product_id: L'identifiant numerique du produit (champ "id" de
            list_products). C'est ce meme identifiant qui est utilise pour
            associer le produit a une quantite de stock.

    Returns:
        Un dictionnaire contenant:
        - success (bool): indique si l'appel a reussi.
        - product (dict ou null): les details du produit si trouve.
        - error (str ou null): message d'erreur clair si le produit n'a
          pas ete trouve, ou si l'appel a echoue (ex: Product API
          injoignable).
    """
    try:
        product = fetch_product_by_id(str(product_id))
        return {
            "success": True,
            "product": product,
            "error": None,
        }
    except ProductNotFoundError as e:
        return {
            "success": False,
            "product": None,
            "error": e.message,
        }
    except ProductAPIError as e:
        return {
            "success": False,
            "product": None,
            "error": e.message,
        }


if __name__ == "__main__":
    import os

    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=int(os.getenv("MCP_PORT", "8001")),
        )
    else:
        mcp.run()
