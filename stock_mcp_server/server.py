"""Stock MCP Server.
Expose des tools MCP en LECTURE SEULE sur la table stock, pour permettre a
l'agent IA de repondre a des questions publiques (via le Client Web) sans
jamais pouvoir modifier le stock. Toute ecriture reste reservee au
Backoffice authentifie.
"""

from fastmcp import FastMCP
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from db import SessionLocal
from models import Branch, Stock

mcp = FastMCP("stock-mcp-server")


def _format_db_error(e: Exception) -> str:
    """Transforme une exception SQLAlchemy en message clair pour l'agent IA,
    sans exposer la stack technique brute (URL de connexion, hints internes...).
    """
    if isinstance(e, OperationalError):
        return (
            "Impossible de se connecter a la base de donnees. "
            "Verifiez que le service de base de donnees est demarre et accessible."
        )
    return f"Erreur lors de l'interrogation de la base de donnees: {type(e).__name__}."


@mcp.tool()
def get_stock_by_product(product_id: int) -> dict:
    """Liste les succursales ayant un produit donne en stock, avec la quantite.

    Utiliser cet outil lorsque l'utilisateur demande ou trouver un produit
    precis, ou combien d'unites sont disponibles et dans quelle(s)
    succursale(s). Pour verifier la disponibilite de PLUSIEURS produits a
    la fois (ex: une liste d'achats), utiliser plutot `check_availability`.
    Pour savoir ce qui est en stock dans une succursale donnee, utiliser
    plutot `get_stock_by_branch`.

    Args:
        product_id: L'identifiant numerique du produit (meme id que celui
            retourne par le Product MCP Server, champ "id").

    Returns:
        Un dictionnaire contenant:
        - success (bool): indique si l'appel a reussi.
        - product_id (int): l'identifiant demande, rappele pour reference.
        - branches (list): une entree par succursale ayant du stock pour
          ce produit, avec branch_id, branch_name, city, quantity. Liste
          vide si aucune succursale n'a ce produit en stock (ce n'est pas
          une erreur).
        - error (str ou null): message d'erreur clair si l'appel a echoue
          (ex: base de donnees injoignable).
    """
    session = SessionLocal()
    try:
        rows = (
            session.query(Stock, Branch)
            .join(Branch, Stock.branch_id == Branch.id)
            .filter(Stock.product_id == product_id, Branch.is_active.is_(True))
            .all()
        )
        branches = [
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "city": branch.city,
                "quantity": stock.quantity,
            }
            for stock, branch in rows
        ]
        return {
            "success": True,
            "product_id": product_id,
            "branches": branches,
            "error": None,
        }
    except SQLAlchemyError as e:
        return {
            "success": False,
            "product_id": product_id,
            "branches": [],
            "error": _format_db_error(e),
        }
    finally:
        session.close()


@mcp.tool()
def list_branches() -> dict:
    """Liste toutes les succursales actives (id, nom, ville).

    Utiliser cet outil pour resoudre le nom ou la ville d'une succursale
    (ex: "Frejus") vers son branch_id, avant get_stock_by_branch.
    """
    session = SessionLocal()
    try:
        rows = session.query(Branch).filter(Branch.is_active.is_(True)).all()
        branches = [{"branch_id": b.id, "name": b.name, "city": b.city} for b in rows]
        return {"success": True, "branches": branches, "error": None}
    except SQLAlchemyError as e:
        return {"success": False, "branches": [], "error": _format_db_error(e)}
    finally:
        session.close()


@mcp.tool()
def get_stock_by_branch(branch_id: int) -> dict:
    """Liste tous les produits en stock dans une succursale donnee, avec leur quantite.

    Utiliser cet outil lorsque l'utilisateur demande quels produits sont
    disponibles dans une succursale precise. Pour savoir dans quelle(s)
    succursale(s) trouver un produit donne, utiliser plutot
    `get_stock_by_product`.

    Args:
        branch_id: L'identifiant numerique de la succursale.

    Returns:
        Un dictionnaire contenant:
        - success (bool): indique si l'appel a reussi.
        - branch_id (int): l'identifiant demande, rappele pour reference.
        - branch_name (str ou null): le nom de la succursale si elle existe.
        - products (list): une entree par produit en stock, avec
          product_id et quantity. Liste vide si la succursale n'a rien en
          stock.
        - error (str ou null): message d'erreur clair si la succursale
          n'existe pas, ou si l'appel a echoue.
    """
    session = SessionLocal()
    try:
        branch = (
            session.query(Branch)
            .filter(Branch.id == branch_id, Branch.is_active.is_(True))
            .first()
        )
        if branch is None:
            return {
                "success": False,
                "branch_id": branch_id,
                "branch_name": None,
                "products": [],
                "error": f"Aucune succursale active trouvee avec l'identifiant {branch_id}.",
            }

        rows = session.query(Stock).filter(Stock.branch_id == branch_id).all()
        products = [
            {"product_id": row.product_id, "quantity": row.quantity} for row in rows
        ]
        return {
            "success": True,
            "branch_id": branch_id,
            "branch_name": branch.name,
            "products": products,
            "error": None,
        }
    except SQLAlchemyError as e:
        return {
            "success": False,
            "branch_id": branch_id,
            "branch_name": None,
            "products": [],
            "error": _format_db_error(e),
        }
    finally:
        session.close()


@mcp.tool()
def check_availability(items: list[dict]) -> dict:
    """Verifie quelle(s) succursale(s) peuvent satisfaire une liste d'achats.

    Utiliser cet outil lorsque l'utilisateur demande dans quelle(s)
    succursale(s) il peut trouver PLUSIEURS produits en une seule fois
    (ex: "je veux 3 unites de X et 2 unites de Y, ou aller ?"). Pour
    verifier la disponibilite d'un seul produit, utiliser plutot
    `get_stock_by_product`.

    Args:
        items: Liste d'objets {"product_id": int, "quantity": int}
            representant ce que l'utilisateur veut acheter. Exemple:
            [{"product_id": 1, "quantity": 3}, {"product_id": 4, "quantity": 2}]

    Returns:
        Un dictionnaire contenant:
        - success (bool): indique si l'appel a reussi.
        - fully_available_branches (list): succursales qui, a elles
          seules, ont assez de stock pour TOUS les produits demandes
          (branch_id, branch_name, city).
        - per_branch_breakdown (list): pour chaque succursale ayant au
          moins un des produits demandes, le detail de ce qu'elle peut
          fournir (branch_id, branch_name, items avec product_id,
          requested, available, sufficient).
        - error (str ou null): message d'erreur clair si l'appel a echoue.
    """
    if not items:
        return {
            "success": False,
            "fully_available_branches": [],
            "per_branch_breakdown": [],
            "error": "items ne doit pas etre une liste vide.",
        }

    session = SessionLocal()
    try:
        product_ids = [item["product_id"] for item in items]
        requested_by_product = {item["product_id"]: item["quantity"] for item in items}

        rows = (
            session.query(Stock, Branch)
            .join(Branch, Stock.branch_id == Branch.id)
            .filter(Stock.product_id.in_(product_ids), Branch.is_active.is_(True))
            .all()
        )

        by_branch: dict[int, dict] = {}
        for stock, branch in rows:
            entry = by_branch.setdefault(
                branch.id,
                {"branch_id": branch.id, "branch_name": branch.name, "city": branch.city, "items": {}},
            )
            entry["items"][stock.product_id] = stock.quantity

        per_branch_breakdown = []
        fully_available_branches = []

        for branch_id, data in by_branch.items():
            item_details = []
            branch_has_everything = True
            for product_id, requested_qty in requested_by_product.items():
                available_qty = data["items"].get(product_id, 0)
                sufficient = available_qty >= requested_qty
                if not sufficient:
                    branch_has_everything = False
                item_details.append({
                    "product_id": product_id,
                    "requested": requested_qty,
                    "available": available_qty,
                    "sufficient": sufficient,
                })

            per_branch_breakdown.append({
                "branch_id": data["branch_id"],
                "branch_name": data["branch_name"],
                "city": data["city"],
                "items": item_details,
            })

            if branch_has_everything:
                fully_available_branches.append({
                    "branch_id": data["branch_id"],
                    "branch_name": data["branch_name"],
                    "city": data["city"],
                })

        return {
            "success": True,
            "fully_available_branches": fully_available_branches,
            "per_branch_breakdown": per_branch_breakdown,
            "error": None,
        }
    except SQLAlchemyError as e:
        return {
            "success": False,
            "fully_available_branches": [],
            "per_branch_breakdown": [],
            "error": _format_db_error(e),
        }
    finally:
        session.close()


if __name__ == "__main__":
    import os

    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(
            transport="http",
            host="0.0.0.0",
            port=int(os.getenv("MCP_PORT", "8003")),
        )
    else:
        mcp.run()