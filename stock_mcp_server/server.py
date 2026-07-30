"""Stock MCP Server.
Expose des tools MCP en LECTURE SEULE sur la table stock, pour permettre a
l'agent IA de repondre a des questions publiques (via le Client Web) sans
jamais pouvoir modifier le stock. Toute ecriture reste reservee au
Backoffice authentifie.
"""

import unicodedata

from fastmcp import FastMCP
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from db import SessionLocal
from models import Branch, Stock

mcp = FastMCP("stock-mcp-server")

FIND_BRANCHES_DESCRIPTION = (
    "Recherche les succursales actives par nom ou ville, sans tenir compte "
    "de la casse ni des accents. Une valeur vide les liste toutes."
)
STOCK_BY_BRANCH_NAME_DESCRIPTION = (
    "Retourne directement les product_id et quantités en stock dans une "
    "succursale recherchée par nom ou ville. À utiliser quand la question "
    "mentionne un lieu comme Fréjus."
)
STOCK_BY_PRODUCT_DESCRIPTION = (
    "Retourne les succursales et quantités disponibles pour un product_id."
)
STOCK_BY_BRANCH_DESCRIPTION = (
    "Retourne les product_id et quantités d'une succursale dont le branch_id "
    "est déjà connu."
)
AVAILABILITY_DESCRIPTION = (
    "Vérifie une liste d'achats [{product_id, quantity}] et calcule les "
    "succursales à visiter, le plan de retrait et les quantités manquantes."
)


def _is_positive_integer(value: object) -> bool:
    """Indique si une valeur est un entier strictement positif."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _normalize_name(value: str) -> str:
    """Minuscule, sans accent et sans espaces superflus.

    Permet de comparer un nom saisi librement ("frejus centre") au nom
    reel stocke en base ("Frejus Centre" avec accent). Le nombre de
    succursales est tres faible, la comparaison se fait donc en Python
    plutot qu'en SQL, ce qui evite de dependre d'une extension
    PostgreSQL absente de SQLite.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().split())


def _matching_active_branches(session, name: str) -> list[Branch]:
    """Retourne les succursales actives correspondant au nom ou à la ville."""
    needle = _normalize_name(name)
    rows = (
        session.query(Branch)
        .filter(Branch.is_active.is_(True))
        .order_by(Branch.id)
        .all()
    )
    return [
        branch
        for branch in rows
        if (
            not needle
            or needle in _normalize_name(branch.name)
            or needle in _normalize_name(branch.city)
        )
    ]


def _stock_products(session, branch_id: int) -> list[dict]:
    """Retourne les quantités strictement positives d'une succursale."""
    rows = (
        session.query(Stock)
        .filter(
            Stock.branch_id == branch_id,
            Stock.quantity > 0,
        )
        .order_by(Stock.product_id)
        .all()
    )
    return [
        {
            "product_id": row.product_id,
            "quantity": row.quantity,
        }
        for row in rows
    ]


def _validate_requested_items(
    items: list[dict],
) -> tuple[dict[int, int] | None, str | None]:
    """Valide et normalise une liste de produits demandés."""
    if not isinstance(items, list) or not items:
        return None, "items doit être une liste non vide."

    requested: dict[int, int] = {}
    for item in items:
        if not isinstance(item, dict):
            return None, "Chaque élément de items doit être un objet."

        product_id = item.get("product_id")
        quantity = item.get("quantity")
        if not _is_positive_integer(product_id):
            return None, "Chaque product_id doit être un entier positif."
        if not _is_positive_integer(quantity):
            return None, "Chaque quantity doit être un entier positif."
        if product_id in requested:
            return None, (
                f"Le produit {product_id} est présent plusieurs fois."
            )
        requested[product_id] = quantity

    return requested, None


def _build_pickup_plan(
    requested_by_product: dict[int, int],
    stock_by_branch: dict[int, dict],
) -> list[dict]:
    """Repartit la commande entre une ou plusieurs succursales.

    Heuristique gloutonne volontairement simple et DETERMINISTE : a
    chaque tour on retient la succursale qui couvre le plus d'unites
    encore manquantes ; a egalite, c'est le plus petit branch_id qui
    gagne. On s'arrete des qu'aucune succursale n'apporte d'unite
    supplementaire.

    Elle cherche a LIMITER le nombre de succursales a visiter, sans
    garantir mathematiquement le minimum : sur certaines repartitions
    elle retient un arret evitable. Le plan produit reste valide (aucune
    succursale visitee deux fois, jamais plus que le stock disponible)
    et identique d'un appel a l'autre, ce qui suffit a l'usage vise.

    Une succursale capable de fournir toute la commande couvre par
    construction le maximum d'unites : elle est donc choisie seule, au
    premier tour, sans traitement particulier.
    """
    remaining = dict(requested_by_product)
    already_visited: set[int] = set()
    plan: list[dict] = []

    while any(quantity > 0 for quantity in remaining.values()):
        best_branch_id = None
        best_units = 0
        for branch_id in sorted(stock_by_branch):
            if branch_id in already_visited:
                continue
            available = stock_by_branch[branch_id]["items"]
            units = sum(
                min(available.get(product_id, 0), quantity)
                for product_id, quantity in remaining.items()
            )
            if units > best_units:
                best_units = units
                best_branch_id = branch_id

        if best_branch_id is None:
            break

        already_visited.add(best_branch_id)
        branch = stock_by_branch[best_branch_id]
        to_pick_up = []
        for product_id in sorted(remaining):
            available = branch["items"].get(product_id, 0)
            quantity = min(available, remaining[product_id])
            if quantity <= 0:
                continue
            to_pick_up.append({
                "product_id": product_id,
                "quantity": quantity,
                "available": available,
            })
            remaining[product_id] -= quantity

        plan.append({
            "branch_id": best_branch_id,
            "branch_name": branch["branch_name"],
            "city": branch["city"],
            "items": to_pick_up,
        })

    return plan


def _unfulfillable_items(
    requested_by_product: dict[int, int],
    plan: list[dict],
) -> list[dict]:
    """Liste ce que le plan de retrait ne parvient pas a couvrir."""
    covered = {product_id: 0 for product_id in requested_by_product}
    for stop in plan:
        for item in stop["items"]:
            covered[item["product_id"]] += item["quantity"]

    return [
        {
            "product_id": product_id,
            "requested": requested_by_product[product_id],
            "covered": covered[product_id],
            "missing": requested_by_product[product_id] - covered[product_id],
        }
        for product_id in sorted(requested_by_product)
        if covered[product_id] < requested_by_product[product_id]
    ]


def _format_db_error(e: Exception) -> str:
    """Transforme une exception SQLAlchemy en message clair pour l'agent IA,
    sans exposer la stack technique brute.
    """
    if isinstance(e, OperationalError):
        return (
            "Impossible de se connecter a la base de donnees. "
            "Verifiez que le service de base de donnees est demarre "
            "et accessible."
        )
    error_type = type(e).__name__
    return (
        "Erreur lors de l'interrogation de la base de donnees: "
        f"{error_type}."
    )


@mcp.tool(description=FIND_BRANCHES_DESCRIPTION)
def find_branches(name: str = "") -> dict:
    """Retrouve l'identifiant d'une succursale a partir de son nom.

    Utiliser cet outil AVANT `get_stock_by_branch` quand l'utilisateur
    designe une succursale par son nom ou sa ville ("le magasin de
    Frejus") et non par son identifiant numerique. Laisser `name` vide
    pour lister toutes les succursales actives.

    La recherche accepte un nom partiel, ignore la casse et les accents:
    "frejus", "FREJUS" et "Frejus Centre" trouvent tous "Frejus Centre".

    Args:
        name: Fragment du nom recherche. Vide = lister tout.

    Returns:
        Un dictionnaire contenant:
        - success (bool): indique si l'appel a reussi.
        - query (str): le texte recherche, rappele pour reference.
        - count (int): nombre de succursales trouvees.
        - branches (list): une entree par succursale active
          correspondante, avec branch_id, branch_name et city, triee par
          branch_id. Liste vide si aucun nom ne correspond (ce n'est pas
          une erreur : il faut alors le dire a l'utilisateur plutot que
          d'inventer une succursale).
        - error (str ou null): message d'erreur clair si l'appel a echoue
          (ex: base de donnees injoignable).
    """
    if not isinstance(name, str):
        return {
            "success": False,
            "query": name,
            "count": 0,
            "branches": [],
            "error": "name doit être une chaîne de caractères.",
        }

    session = SessionLocal()
    try:
        rows = _matching_active_branches(session, name)
        branches = [
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "city": branch.city,
            }
            for branch in rows
        ]
        return {
            "success": True,
            "query": name,
            "count": len(branches),
            "branches": branches,
            "error": None,
        }
    except SQLAlchemyError as e:
        return {
            "success": False,
            "query": name,
            "count": 0,
            "branches": [],
            "error": _format_db_error(e),
        }
    finally:
        session.close()


@mcp.tool(description=STOCK_BY_BRANCH_NAME_DESCRIPTION)
def get_stock_by_branch_name(name: str) -> dict:
    """Retourne en un appel les stocks des succursales correspondant au lieu.

    Cette façade évite à l'agent un aller-retour LLM entre `find_branches`
    et `get_stock_by_branch`. La recherche conserve exactement les mêmes
    règles de casse, d'accents et de correspondance partielle.
    """
    if not isinstance(name, str) or not name.strip():
        return {
            "success": False,
            "query": name,
            "count": 0,
            "branches": [],
            "error": "name doit être une chaîne de caractères non vide.",
        }

    session = SessionLocal()
    try:
        branches = [
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "city": branch.city,
                "products": _stock_products(session, branch.id),
            }
            for branch in _matching_active_branches(session, name)
        ]
        return {
            "success": True,
            "query": name,
            "count": len(branches),
            "branches": branches,
            "error": None,
        }
    except SQLAlchemyError as e:
        return {
            "success": False,
            "query": name,
            "count": 0,
            "branches": [],
            "error": _format_db_error(e),
        }
    finally:
        session.close()


@mcp.tool(description=STOCK_BY_PRODUCT_DESCRIPTION)
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
    if not _is_positive_integer(product_id):
        return {
            "success": False,
            "product_id": product_id,
            "branches": [],
            "error": "product_id doit être un entier positif.",
        }

    session = SessionLocal()
    try:
        rows = (
            session.query(Stock, Branch)
            .join(Branch, Stock.branch_id == Branch.id)
            .filter(
                Stock.product_id == product_id,
                Stock.quantity > 0,
                Branch.is_active.is_(True),
            )
            .order_by(Branch.id)
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


@mcp.tool(description=STOCK_BY_BRANCH_DESCRIPTION)
def get_stock_by_branch(branch_id: int) -> dict:
    """Liste les produits en stock dans une succursale et leur quantite.

    Utiliser cet outil lorsque l'utilisateur demande quels produits sont
    disponibles dans une succursale precise. Si seul le NOM de la
    succursale est connu, appeler d'abord `find_branches` pour obtenir
    son identifiant. Pour savoir dans quelle(s) succursale(s) trouver un
    produit donne, utiliser plutot `get_stock_by_product`.

    Args:
        branch_id: L'identifiant numerique de la succursale (champ
            "branch_id" retourne par `find_branches`).

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
    if not _is_positive_integer(branch_id):
        return {
            "success": False,
            "branch_id": branch_id,
            "branch_name": None,
            "products": [],
            "error": "branch_id doit être un entier positif.",
        }

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
                "error": (
                    "Aucune succursale active trouvée avec l'identifiant "
                    f"{branch_id}."
                ),
            }

        products = _stock_products(session, branch_id)
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


@mcp.tool(description=AVAILABILITY_DESCRIPTION)
def check_availability(items: list[dict]) -> dict:
    """Verifie quelle(s) succursale(s) peuvent satisfaire une liste d'achats.

    Utiliser cet outil lorsque l'utilisateur demande dans quelle(s)
    succursale(s) il peut trouver PLUSIEURS produits en une seule fois
    (ex: "je veux 3 unites de X et 2 unites de Y, ou aller ?"). Pour
    verifier la disponibilite d'un seul produit, utiliser plutot
    `get_stock_by_product`.

    L'outil privilegie toujours UNE seule succursale quand l'une d'elles
    peut tout fournir. Sinon il calcule une repartition sur plusieurs
    succursales (`pickup_plan`) et signale ce qui reste introuvable
    (`unfulfillable`).

    Args:
        items: Liste d'objets {"product_id": int, "quantity": int}
            representant ce que l'utilisateur veut acheter. Exemple:
            [{"product_id": 1, "quantity": 3},
             {"product_id": 4, "quantity": 2}]

    Returns:
        Un dictionnaire contenant:
        - success (bool): indique si l'appel a reussi.
        - fully_available_branches (list): succursales qui, a elles
          seules, ont assez de stock pour TOUS les produits demandes
          (branch_id, branch_name, city). Si cette liste n'est pas vide,
          repondre en priorite avec UNE de ces succursales.
        - pickup_plan (list): repartition a suivre quand aucune
          succursale ne suffit seule. Une entree par succursale a
          visiter, dans l'ordre : branch_id, branch_name, city, et items
          = [{product_id, quantity (a retirer ici), available (stock de
          cette succursale)}]. Contient une seule entree lorsqu'une
          succursale suffit.
        - branches_needed (int): nombre de succursales du pickup_plan.
        - fully_covered (bool): True si le pickup_plan couvre toute la
          commande.
        - unfulfillable (list): ce qui reste introuvable, avec
          product_id, requested, covered et missing. Le dire clairement
          a l'utilisateur, ne jamais le passer sous silence.
        - per_branch_breakdown (list): pour chaque succursale ayant au
          moins un des produits demandes, le detail de ce qu'elle peut
          fournir (branch_id, branch_name, items avec product_id,
          requested, available, sufficient).
        - error (str ou null): message d'erreur clair si l'appel a echoue.
    """
    requested_by_product, validation_error = _validate_requested_items(items)
    if validation_error:
        return {
            "success": False,
            "fully_available_branches": [],
            "pickup_plan": [],
            "branches_needed": 0,
            "fully_covered": False,
            "unfulfillable": [],
            "per_branch_breakdown": [],
            "error": validation_error,
        }

    session = SessionLocal()
    try:
        product_ids = list(requested_by_product)

        rows = (
            session.query(Stock, Branch)
            .join(Branch, Stock.branch_id == Branch.id)
            .filter(
                Stock.product_id.in_(product_ids),
                Stock.quantity > 0,
                Branch.is_active.is_(True),
            )
            .order_by(Branch.id, Stock.product_id)
            .all()
        )

        by_branch: dict[int, dict] = {}
        for stock, branch in rows:
            entry = by_branch.setdefault(
                branch.id,
                {
                    "branch_id": branch.id,
                    "branch_name": branch.name,
                    "city": branch.city,
                    "items": {},
                },
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
                item_details.append(
                    {
                        "product_id": product_id,
                        "requested": requested_qty,
                        "available": available_qty,
                        "sufficient": sufficient,
                    }
                )

            per_branch_breakdown.append(
                {
                    "branch_id": data["branch_id"],
                    "branch_name": data["branch_name"],
                    "city": data["city"],
                    "items": item_details,
                }
            )

            if branch_has_everything:
                fully_available_branches.append(
                    {
                        "branch_id": data["branch_id"],
                        "branch_name": data["branch_name"],
                        "city": data["city"],
                    }
                )

        pickup_plan = _build_pickup_plan(requested_by_product, by_branch)
        unfulfillable = _unfulfillable_items(requested_by_product, pickup_plan)

        return {
            "success": True,
            "fully_available_branches": fully_available_branches,
            "pickup_plan": pickup_plan,
            "branches_needed": len(pickup_plan),
            "fully_covered": not unfulfillable,
            "unfulfillable": unfulfillable,
            "per_branch_breakdown": per_branch_breakdown,
            "error": None,
        }
    except SQLAlchemyError as e:
        return {
            "success": False,
            "fully_available_branches": [],
            "pickup_plan": [],
            "branches_needed": 0,
            "fully_covered": False,
            "unfulfillable": [],
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
