"""Jeu de données de démonstration relançable.

Par défaut, complète les données manquantes sans supprimer les comptes,
succursales ou stocks existants. L'option ``--reset`` reconstruit
volontairement le jeu de démonstration depuis zéro.
"""

import argparse
import os

from argon2 import PasswordHasher
from sqlalchemy import select

from db import SessionLocal
from models import Branch, Stock, User, UserRole

hasher = PasswordHasher()

DEFAULT_ADMIN_PASSWORD = "ChangeMe123!"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)

# Mot de passe commun aux comptes de démonstration (jamais de production).
COMMON_PASSWORD = os.environ.get("SEED_USER_PASSWORD", "Test123!")

# Villes phonétiquement distinctes pour tester l'agent IA.
BRANCHES = [
    {"name": "Fréjus Centre", "city": "Fréjus"},
    {"name": "Laval Gare", "city": "Laval"},
    {"name": "Toulouse Capitole", "city": "Toulouse"},
]

COMMON_USERS = [
    {"username": "marie", "branch": "Fréjus Centre"},
    {"username": "paul", "branch": "Laval Gare"},
]

# Scénario demandé dans la consigne :
# "Je veux acheter 3 unités de X, 2 de Y et 4 de Z, où aller ?"
# Fréjus Centre est la seule succursale pouvant satisfaire seule cette liste.
DEMO_BRANCH_NAME = "Fréjus Centre"
DEMO_SHOPPING_LIST = [
    {
        "product_id": 1,
        "name": "Holberton Student Laptop 14",
        "quantity": 3,
    },
    {
        "product_id": 3,
        "name": "27 inch Lab Monitor",
        "quantity": 2,
    },
    {
        "product_id": 7,
        "name": "Compact Keyboard ES",
        "quantity": 4,
    },
]
DEMO_STOCK_MINIMUMS = {
    item["product_id"]: item["quantity"]
    for item in DEMO_SHOPPING_LIST
}

# product_id -> quantité. Identifiants issus de la Product API (1 à 40).
#
# Jeu conçu pour couvrir les questions du sujet :
#   - produits 1, 3, 7, 9, 15, 21 présents dans plusieurs succursales
#     -> "quelle succursale a le produit X ?" a plusieurs réponses
#   - Fréjus détient au minimum 3 produits 1, 2 produits 3 et 4 produits 7
#     -> le scénario d'achat multi-produits a une réponse déterministe
#   - produit 38 : présent dans une seule succursale
#   - produit 32 : marqué discontinued côté API, exclu de /products par défaut
#     -> on a du stock d'un produit que l'agent ne trouve pas naïvement
#   - quantités à 0 (produit 4 à Fréjus, 15 à Laval) : vérifie le
#     filtre quantity > 0
#   - la majorité du catalogue n'est nulle part -> "indisponible"
#     doit rester une réponse possible
STOCK = {
    "Fréjus Centre": {
        1: 5, 2: 14, 3: 12, 4: 0, 5: 7, 6: 33, 7: 8, 8: 2, 10: 19,
        11: 0, 12: 41, 13: 6, 14: 22, 15: 3, 16: 9, 17: 1, 18: 27,
        19: 15, 20: 0, 22: 11, 23: 4, 25: 18, 28: 7, 30: 13, 32: 4,
        35: 9,
    },
    "Laval Gare":        {1: 2,  3: 7,  9: 20, 15: 0, 21: 6},
    "Toulouse Capitole": {4: 11, 7: 1,  9: 5,  21: 14, 38: 9},
}


def wipe(session) -> None:
    """Supprime les données existantes pour le mode ``--reset``.

    L'ordre compte : les clés étrangères sont en ON DELETE RESTRICT,
    on doit donc supprimer les tables qui référencent avant celles
    qui sont référencées.
    """
    session.query(Stock).delete()
    session.query(User).delete()
    session.query(Branch).delete()


def _check_demo_configuration() -> None:
    """Vérifie la cohérence du jeu de démonstration avant de l'appliquer.

    ``_ensure_users`` et ``_ensure_stock`` retrouvent leur succursale par
    son nom : un nom absent de ``BRANCHES`` provoquerait un ``KeyError``
    illisible au démarrage du conteneur. On le signale ici, avec le nom
    fautif, et on garantit au passage les deux succursales minimum dont
    la démonstration multi-succursales a besoin.
    """
    known = {data["name"] for data in BRANCHES}
    if len(known) < 2:
        raise ValueError(
            "La démonstration exige au moins deux succursales distinctes."
        )

    referenced = {data["branch"] for data in COMMON_USERS}
    referenced.update(STOCK)
    referenced.add(DEMO_BRANCH_NAME)
    unknown = sorted(referenced - known)
    if unknown:
        raise ValueError(
            "Succursale(s) absente(s) de BRANCHES : " + ", ".join(unknown)
        )


def _ensure_branches(session, stats: dict[str, int]) -> dict[str, Branch]:
    """Retourne les succursales de seed, en créant celles qui manquent."""
    names = [data["name"] for data in BRANCHES]
    branches = {
        branch.name: branch
        for branch in session.execute(
            select(Branch).where(Branch.name.in_(names))
        ).scalars()
    }

    for data in BRANCHES:
        if data["name"] in branches:
            continue
        branch = Branch(name=data["name"], city=data["city"])
        branches[data["name"]] = branch
        session.add(branch)
        stats["branches_created"] += 1

    session.flush()
    return branches


def _ensure_users(
    session,
    branches: dict[str, Branch],
    stats: dict[str, int],
) -> None:
    """Crée uniquement les comptes de démonstration absents."""
    usernames = [ADMIN_USERNAME]
    usernames.extend(data["username"] for data in COMMON_USERS)
    existing = set(
        session.execute(
            select(User.username).where(User.username.in_(usernames))
        ).scalars()
    )

    if ADMIN_USERNAME not in existing:
        session.add(User(
            username=ADMIN_USERNAME,
            password_hash=hasher.hash(ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            branch=None,
        ))
        stats["users_created"] += 1

    for data in COMMON_USERS:
        if data["username"] in existing:
            continue
        session.add(User(
            username=data["username"],
            password_hash=hasher.hash(COMMON_PASSWORD),
            role=UserRole.COMMON,
            branch=branches[data["branch"]],
        ))
        stats["users_created"] += 1


def _ensure_stock(
    session,
    branches: dict[str, Branch],
    stock_data: dict[str, dict[int, int]],
    stats: dict[str, int],
) -> None:
    """Crée uniquement les lignes de stock de démonstration absentes."""
    for branch_name, items in stock_data.items():
        branch = branches[branch_name]
        product_ids = list(items)
        existing = {
            stock.product_id: stock
            for stock in session.execute(
                select(Stock)
                .where(Stock.branch_id == branch.id)
                .where(Stock.product_id.in_(product_ids))
            ).scalars()
        }

        for product_id, quantity in items.items():
            if product_id not in existing:
                session.add(Stock(
                    branch=branch,
                    product_id=product_id,
                    quantity=quantity,
                ))
                stats["stock_created"] += 1


def seed(session) -> dict[str, int]:
    """Fusionne les données de démonstration dans la base courante.

    Toute succursale, tout compte ou toute ligne de stock manquante est
    créé. Les données déjà présentes, notamment les quantités de stock,
    ne sont jamais modifiées.
    """
    _check_demo_configuration()
    stats = {
        "branches_created": 0,
        "users_created": 0,
        "stock_created": 0,
        # Clé conservée pour les consommateurs existants des statistiques.
        # Une seed normale ne relève désormais plus aucun stock.
        "stock_increased": 0,
    }

    branches = _ensure_branches(session, stats)
    _ensure_users(session, branches, stats)
    _ensure_stock(session, branches, STOCK, stats)
    return stats


def _demo_question() -> str:
    """Construit la question naturelle correspondant aux données de test."""
    parts = [
        f"{item['quantity']} unités de {item['name']}"
        for item in DEMO_SHOPPING_LIST
    ]
    return (
        f"Si je veux acheter {parts[0]}, {parts[1]} et {parts[2]}, "
        "quelle succursale dois-je visiter ?"
    )


def main(reset: bool = False) -> None:
    """Applique la seed en fusion ou, explicitement, après remise à zéro."""
    with SessionLocal() as session:
        if reset:
            wipe(session)
        admin_will_be_created = session.execute(
            select(User.id).where(User.username == ADMIN_USERNAME)
        ).first() is None
        stats = seed(session)
        session.commit()

    if admin_will_be_created and ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
        print(
            "ATTENTION : ADMIN_PASSWORD non défini, "
            "mot de passe par défaut utilisé."
        )

    mode = "réinitialisation" if reset else "fusion sans suppression"
    print(
        f"Seed terminée ({mode}) : "
        f"{stats['branches_created']} succursale(s), "
        f"{stats['users_created']} utilisateur(s) et "
        f"{stats['stock_created']} ligne(s) de stock créés."
    )
    print("Question de démonstration :", _demo_question())
    print("Réponse attendue :", DEMO_BRANCH_NAME)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="supprime les données existantes avant de recréer la démo",
    )
    main(reset=parser.parse_args().reset)
