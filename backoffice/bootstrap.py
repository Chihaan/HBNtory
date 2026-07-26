"""Initialise le backoffice.

Ajoute les données de démonstration uniquement sur une base vide.
"""

from sqlalchemy import select

from db import SessionLocal
from init_db import configure_readonly_role, create_tables
from models import User
from seed import main as seed_database


def has_users() -> bool:
    """Indique si la base contient déjà au moins un utilisateur."""
    with SessionLocal() as session:
        return session.execute(
            select(User.id).limit(1)
        ).first() is not None


def main() -> None:
    """Prépare le schéma puis seed uniquement une base sans utilisateur."""
    create_tables()
    configure_readonly_role()

    if has_users():
        print("Données existantes conservées.")
        return

    print("Base vide : insertion des données de démonstration...")
    seed_database()


if __name__ == "__main__":
    main()
