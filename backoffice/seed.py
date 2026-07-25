"""Jeu de données de démonstration.

Crée l'administrateur, les succursales et du stock de test.
À lancer APRÈS init_db.py. Relançable : les données existantes sont remplacées.
"""

import os

from argon2 import PasswordHasher

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

# product_id -> quantité. Identifiants issus de la Product API (1 à 40).
#
# Jeu conçu pour couvrir les questions du sujet :
#   - produits 1, 3, 7, 9, 15, 21 présents dans plusieurs succursales
#     -> "quelle succursale a le produit X ?" a plusieurs réponses
#   - aucune succursale ne détient à la fois 1, 3 et 15
#     -> "où acheter X, Y et Z ?" oblige à en proposer plusieurs
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
    """Supprime les données existantes.

    L'ordre compte : les clés étrangères sont en ON DELETE RESTRICT,
    on doit donc supprimer les tables qui référencent avant celles
    qui sont référencées.
    """
    session.query(Stock).delete()
    session.query(User).delete()
    session.query(Branch).delete()


def seed(session) -> None:
    """Insère les données de démonstration."""
    branches = {}
    for data in BRANCHES:
        branch = Branch(name=data["name"], city=data["city"])
        session.add(branch)
        branches[data["name"]] = branch

    session.add(
        User(
            username=ADMIN_USERNAME,
            password_hash=hasher.hash(ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            branch=None,
        )
    )

    for data in COMMON_USERS:
        session.add(
            User(
                username=data["username"],
                password_hash=hasher.hash(COMMON_PASSWORD),
                role=UserRole.COMMON,
                branch=branches[data["branch"]],
            )
        )

    for branch_name, items in STOCK.items():
        for product_id, quantity in items.items():
            session.add(
                Stock(
                    branch=branches[branch_name],
                    product_id=product_id,
                    quantity=quantity,
                )
            )


def main() -> None:
    if ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
        print(
            "ATTENTION : ADMIN_PASSWORD non défini, "
            "mot de passe par défaut utilisé."
        )

    with SessionLocal() as session:
        wipe(session)
        seed(session)
        session.commit()

    stock_lines = sum(len(items) for items in STOCK.values())
    print(
        f"Seed terminé : {len(BRANCHES)} succursales, "
        f"{len(COMMON_USERS) + 1} utilisateurs, "
        f"{stock_lines} lignes de stock"
    )


if __name__ == "__main__":
    main()
