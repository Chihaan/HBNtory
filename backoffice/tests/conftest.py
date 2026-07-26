"""Fixtures partagées de la suite de tests.

La configuration d'environnement (variables lues à l'import par db.py
et services/products.py) est posée AVANT tout import des modules du
projet, sinon ces imports lèveraient KeyError.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("PRODUCTS_API_URL", "http://products.test")
os.environ.setdefault("MCP_DB_PASSWORD", "test-readonly-password")

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402

from db import Base, engine, SessionLocal  # noqa: E402
from models import Branch, User, UserRole  # noqa: E402
import app as app_module  # noqa: E402

ph = PasswordHasher()

# Mots de passe des utilisateurs de test, réutilisés dans les tests
# de connexion.
ADMIN_PASSWORD = "admin-pass"
EMPLOYEE_PASSWORD = "bob-pass"


@pytest.fixture(autouse=True)
def _schema():
    """Schéma vierge avant chaque test, détruit après (isolation)."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session():
    """Session SQLAlchemy branchée sur la base mémoire."""
    with SessionLocal() as sess:
        yield sess


@pytest.fixture
def branch(session):
    """Une succursale persistée."""
    b = Branch(name="Fréjus Centre", city="Fréjus")
    session.add(b)
    session.commit()
    return b


@pytest.fixture
def other_branch(session):
    """Une deuxième succursale (pour tester les changements)."""
    b = Branch(name="Nice Port", city="Nice")
    session.add(b)
    session.commit()
    return b


@pytest.fixture
def admin(session):
    """Un administrateur (sans succursale)."""
    u = User(
        username="admin",
        password_hash=ph.hash(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        branch_id=None,
    )
    session.add(u)
    session.commit()
    return u


@pytest.fixture
def employee(session, branch):
    """Un employé rattaché à `branch`."""
    u = User(
        username="bob",
        password_hash=ph.hash(EMPLOYEE_PASSWORD),
        role=UserRole.COMMON,
        branch_id=branch.id,
    )
    session.add(u)
    session.commit()
    return u


@pytest.fixture
def app():
    """Application Flask en mode test, CSRF désactivé."""
    application = app_module.create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


@pytest.fixture
def client(app):
    """Client HTTP de test Flask."""
    return app.test_client()


@pytest.fixture
def login(client):
    """Fonction de connexion : login(username, password)."""
    def _login(username, password):
        return client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
    return _login
