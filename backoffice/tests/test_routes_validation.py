"""Tests de validation des formulaires (entrées invalides)."""

from db import SessionLocal
from models import Stock, User

ADMIN_PASSWORD = "admin-pass"
EMPLOYEE_PASSWORD = "bob-pass"


def test_add_stock_quantite_non_entiere(client, employee, login):
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.post("/stock/add",
                       data={"product_id": 5, "quantity": "abc"})
    # Formulaire invalide : la route (POST-only) redirige, rien créé
    assert resp.status_code == 302
    assert "/stock" in resp.headers["Location"]
    with SessionLocal() as s:
        assert s.query(Stock).count() == 0


def test_add_stock_quantite_trop_grande(client, employee, login):
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.post(
        "/stock/add",
        data={"product_id": 5, "quantity": "200000000000000000000"},
    )

    assert resp.status_code == 302
    with client.session_transaction() as flask_session:
        flashes = flask_session.get("_flashes", [])
    assert any(
        "entre 1 et 1 000 000" in message
        for category, message in flashes
        if category == "error"
    )
    with SessionLocal() as s:
        assert s.query(Stock).count() == 0


def test_create_user_champs_manquants(client, admin, branch, login):
    login("admin", ADMIN_PASSWORD)
    # branch_id manquant -> formulaire invalide
    resp = client.post("/users/new",
                       data={
                           "username": "sansbranche",
                           "password": "valid-pass",
                       })
    assert resp.status_code == 200
    assert b"invalide" in resp.data
    with SessionLocal() as s:
        count = s.query(User).filter_by(username="sansbranche").count()
        assert count == 0


def test_create_user_mot_de_passe_trop_court(
        client, admin, branch, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post("/users/new", data={
        "username": "carol",
        "password": "court",
        "branch_id": branch.id,
    })

    assert resp.status_code == 200
    assert b"invalide" in resp.data
    with SessionLocal() as s:
        assert s.query(User).filter_by(username="carol").count() == 0


def test_create_user_nom_sans_lettre_ni_chiffre(
        client, admin, branch, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post("/users/new", data={
        "username": "---",
        "password": "valid-pass",
        "branch_id": branch.id,
    })

    assert resp.status_code == 200
    assert "lettre ou un chiffre".encode() in resp.data
    with SessionLocal() as s:
        assert s.query(User).filter_by(username="---").count() == 0
