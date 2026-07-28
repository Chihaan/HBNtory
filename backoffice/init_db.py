"""Crée les tables et configure le rôle de lecture seule du serveur MCP.

À lancer après le démarrage de PostgreSQL. Relançable sans risque.
"""

import os

from sqlalchemy import text

from db import Base, engine
import models  # noqa: F401
from models import MAX_STOCK_QUANTITY

MCP_ROLE = os.environ.get("MCP_DB_USER", "mcp_reader")
MCP_PASSWORD = os.environ["MCP_DB_PASSWORD"]

# Les seules tables que l'agent IA a le droit de lire.
READABLE_TABLES = ("branches", "stock")
STOCK_MAX_CONSTRAINT = "ck_stock_quantity_maximum"


def ensure_stock_limit_constraint() -> None:
    """Ajoute le plafond aux bases PostgreSQL créées avant cette règle."""
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        exists = conn.execute(
            text(
                "SELECT 1 FROM pg_constraint "
                "WHERE conname = :constraint_name"
            ),
            {"constraint_name": STOCK_MAX_CONSTRAINT},
        ).scalar()
        if exists:
            return

        conn.execute(text(
            f'ALTER TABLE "stock" ADD CONSTRAINT '
            f'"{STOCK_MAX_CONSTRAINT}" '
            f"CHECK (quantity <= {MAX_STOCK_QUANTITY})"
        ))
        print(
            "Contrainte de stock ajoutée : maximum "
            f"{MAX_STOCK_QUANTITY} unités."
        )


def configure_readonly_role() -> None:
    """Crée (ou met à jour) le rôle PostgreSQL utilisé par le serveur MCP.

    Le service IA est interrogé par des utilisateurs anonymes. En lui donnant
    un compte dédié sans privilège sur `users`, la restriction devient
    structurelle : la base refuse toute autre opération, quel que soit le code.
    """
    password = MCP_PASSWORD.replace("'", "''")
    database = engine.url.database

    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
            {"name": MCP_ROLE},
        ).scalar()

        action = "ALTER" if exists else "CREATE"
        conn.execute(
            text(f"{action} ROLE \"{MCP_ROLE}\" LOGIN PASSWORD '{password}'")
        )

        conn.execute(
            text(f'GRANT CONNECT ON DATABASE "{database}" TO "{MCP_ROLE}"')
        )
        conn.execute(text(f'GRANT USAGE ON SCHEMA public TO "{MCP_ROLE}"'))

        for table in READABLE_TABLES:
            conn.execute(text(f'GRANT SELECT ON "{table}" TO "{MCP_ROLE}"'))

        conn.execute(text(f'REVOKE ALL ON "users" FROM "{MCP_ROLE}"'))

    print(
        f"Rôle {MCP_ROLE} : SELECT sur {', '.join(READABLE_TABLES)}, "
        "aucun accès à users"
    )


def create_tables() -> None:
    """Crée les tables manquantes. Ne touche pas aux tables existantes."""
    Base.metadata.create_all(engine)
    ensure_stock_limit_constraint()
    print("Tables créées :", ", ".join(Base.metadata.tables))


def main() -> None:
    create_tables()
    configure_readonly_role()


if __name__ == "__main__":
    main()
