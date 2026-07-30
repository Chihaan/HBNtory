"""Base SQLite isolée utilisée par les tests du Stock MCP."""

import os

os.environ.setdefault("MCP_DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from models import Base, Branch, Stock  # noqa: E402
import server  # noqa: E402

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def database(monkeypatch):
    """Crée un catalogue de stock minimal avant chaque test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with TestingSession() as session:
        active = Branch(name="Fréjus Centre", city="Fréjus")
        inactive = Branch(
            name="Ancienne boutique",
            city="Nice",
            is_active=False,
        )
        session.add_all([active, inactive])
        session.flush()
        session.add_all([
            Stock(branch_id=active.id, product_id=1, quantity=5),
            Stock(branch_id=active.id, product_id=2, quantity=0),
            Stock(branch_id=inactive.id, product_id=1, quantity=9),
        ])
        session.commit()

    monkeypatch.setattr(server, "SessionLocal", TestingSession)
    yield
