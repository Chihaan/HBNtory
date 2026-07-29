"""Connexion a la base de donnees pour le Stock MCP Server.

Se connecte via le role PostgreSQL en lecture seule "mcp_reader"
(variable MCP_DATABASE_URL), pas via DATABASE_URL (compte complet du
Backoffice). Ce role, cree par backoffice/init_db.py, ne peut lire que
branches et stock, et ne peut rien ecrire.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# En local (hors Docker Compose), charge les variables depuis .env.
# En Docker, les variables sont deja injectees via env_file: .env dans
# docker-compose.yml, donc cet appel est simplement sans effet.
load_dotenv()


class Base(DeclarativeBase):
    pass


# pool_pre_ping verifie que la connexion a la db est toujours vivante
engine = create_engine(os.environ["MCP_DATABASE_URL"], pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
