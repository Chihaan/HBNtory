"""Harness end-to-end : sert l'app Flask réelle et pilote un navigateur.

Ce dossier n'est PAS dans `testpaths` (voir pytest.ini) : la suite
principale ne le collecte donc pas et ne dépend pas d'un navigateur.
On le lance explicitement avec `pytest e2e/`.
"""

import os
import socket
import tempfile
import threading

os.environ.setdefault("SECRET_KEY", "e2e-secret")
os.environ.setdefault("PRODUCTS_API_URL", "http://products.test")
_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_DB.name}")

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from db import Base, engine, SessionLocal  # noqa: E402
from models import Branch, Stock, User, UserRole  # noqa: E402
import app as app_module  # noqa: E402
import views.stock as stock_view  # noqa: E402

ph = PasswordHasher()

ADMIN_PASSWORD = "admin-pass"


@pytest.fixture(scope="session")
def base_url():
    """Démarre l'app sur un port libre et renvoie son URL."""
    Base.metadata.create_all(engine)
    with SessionLocal() as sess:
        branch = Branch(name="Fréjus Centre", city="Fréjus")
        sess.add(branch)
        sess.flush()
        sess.add(User(
            username="admin",
            password_hash=ph.hash(ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            branch_id=None,
        ))
        sess.add(User(
            username="bob",
            password_hash=ph.hash("bob-pass"),
            role=UserRole.COMMON,
            branch_id=branch.id,
        ))
        sess.add(Stock(
            branch_id=branch.id,
            product_id=1,
            quantity=5,
        ))
        sess.add(Stock(
            branch_id=branch.id,
            product_id=2,
            quantity=0,
        ))
        sess.commit()

    products = [
        {
            "id": 1,
            "sku": "HB-LAP-1001",
            "name": "Ordinateur étudiant",
            "unit_price": 799.0,
            "description": "Ordinateur de démonstration.",
            "category": "Informatique",
        },
        {
            "id": 2,
            "sku": "HB-MON-2101",
            "name": "Écran de laboratoire",
            "unit_price": 229.5,
            "description": "Écran de démonstration.",
            "category": "Écrans",
        },
    ]
    patcher = pytest.MonkeyPatch()
    patcher.setattr(stock_view, "list_products", lambda: products)

    application = app_module.create_app()
    # CSRF actif : on teste le comportement réel du navigateur.

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = make_server("127.0.0.1", port, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        patcher.undo()
