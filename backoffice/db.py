"""Connexion à la base de données."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


_url = os.environ["DATABASE_URL"]

if _url.startswith("sqlite"):
    # Base de test en mémoire : StaticPool force une connexion unique
    # partagée, sinon chaque session verrait une base vide.
    engine = create_engine(
        _url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # pool_pre_ping verife que la connection a la db est toujours vivante
    engine = create_engine(_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
