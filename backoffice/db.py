"""Connexion à la base de données."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


# pool_pre_ping verife que la connection a la db est toujours vivante
engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
