"""Tests de validation des formulaires (entrées invalides)."""

from db import SessionLocal
from models import Stock, User

ADMIN_PASSWORD = "admin-pass"
EMPLOYEE_PASSWORD = "bob-pass"


def test_add_stock_quantite_non_entiere(client, employee, login, monkeypatch):
    import views.stock as stock_view
    # La page de repli appelle list_products : on évite tout réseau
    monkeypatch.setattr(stock_view, "list_products", lambda: [])
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.post("/stock/add",
                       data={"product_id": 5, "quantity": "abc"})
    # Formulaire invalide : pas de redirection, aucune ligne créée
    assert resp.status_code == 200
    with SessionLocal() as s:
        assert s.query(Stock).count() == 0


def test_create_user_champs_manquants(client, admin, branch, login):
    login("admin", ADMIN_PASSWORD)
    # branch_id manquant -> formulaire invalide
    resp = client.post("/users/new",
                       data={"username": "sansbranche", "password": "pw"})
    assert resp.status_code == 200
    assert b"invalide" in resp.data
    with SessionLocal() as s:
        count = s.query(User).filter_by(username="sansbranche").count()
        assert count == 0
