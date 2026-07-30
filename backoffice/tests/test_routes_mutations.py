"""Tests d'intégration des routes de mutation (POST complet)."""

from argon2 import PasswordHasher

from db import SessionLocal
from models import User, Stock, UserRole

ph = PasswordHasher()

ADMIN_PASSWORD = "admin-pass"
EMPLOYEE_PASSWORD = "bob-pass"


# ---------- Utilisateurs (admin) ----------

def test_create_user_ok(client, admin, branch, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post("/users/new", data={
        "username": "carol", "password": "pw-carol",
        "branch_id": branch.id,
    })
    assert resp.status_code == 302
    with SessionLocal() as s:
        u = s.query(User).filter_by(username="carol").one_or_none()
        assert u is not None
        assert u.role == UserRole.COMMON


def test_create_user_nom_pris_rouvre_modale(client, admin, employee, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post("/users/new", data={
        "username": "bob", "password": "valid-pass",
        "branch_id": employee.branch_id,
    })
    # Pas de redirection : la liste est re-rendue avec la modale rouverte
    assert resp.status_code == 200
    assert b"showModal" in resp.data
    with SessionLocal() as s:
        count = s.query(User).filter_by(username="bob").count()
        assert count == 1


def test_delete_user_ok(client, admin, employee, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post(f"/users/{employee.id}/delete")
    assert resp.status_code == 302
    with SessionLocal() as s:
        u = s.get(User, employee.id)
        assert u.deleted_at is not None


def test_change_password_ok(client, admin, employee, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post(f"/users/{employee.id}/password",
                       data={"password": "tout-neuf"})
    assert resp.status_code == 302
    with SessionLocal() as s:
        u = s.get(User, employee.id)
        assert ph.verify(u.password_hash, "tout-neuf")


def test_deactivate_user_ok(client, admin, employee, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post(f"/users/{employee.id}/deactivate")
    assert resp.status_code == 302
    with SessionLocal() as s:
        assert s.get(User, employee.id).is_active is False


def test_activate_user_ok(client, admin, employee, session, login):
    from services.users import set_active
    set_active(session, employee.id, False)
    session.commit()
    login("admin", ADMIN_PASSWORD)
    resp = client.post(f"/users/{employee.id}/activate")
    assert resp.status_code == 302
    with SessionLocal() as s:
        assert s.get(User, employee.id).is_active is True


def test_change_branch_ok(client, admin, employee, other_branch, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post(f"/users/{employee.id}/branch",
                       data={"branch_id": other_branch.id})
    assert resp.status_code == 302
    with SessionLocal() as s:
        u = s.get(User, employee.id)
        assert u.branch_id == other_branch.id


# ---------- Stock (employé) ----------

def test_add_stock_ok(client, employee, login, monkeypatch):
    import services.stock as stock_service
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.post("/stock/add",
                       data={"product_id": 5, "quantity": 7})
    assert resp.status_code == 302
    with SessionLocal() as s:
        st = s.query(Stock).filter_by(
            branch_id=employee.branch_id, product_id=5).one()
        assert st.quantity == 7


def test_remove_stock_ok(client, employee, session, login):
    session.add(Stock(branch_id=employee.branch_id,
                      product_id=5, quantity=10))
    session.commit()
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.post("/stock/remove",
                       data={"product_id": 5, "quantity": 4})
    assert resp.status_code == 302
    with SessionLocal() as s:
        st = s.query(Stock).filter_by(
            branch_id=employee.branch_id, product_id=5).one()
        assert st.quantity == 6


def test_add_stock_erreur_redirige_avec_flash(
        client, employee, login, monkeypatch):
    import services.stock as stock_service
    import views.stock as stock_view
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: False)
    # Évite tout appel réseau réel sur la page de destination
    monkeypatch.setattr(stock_view, "list_products", lambda: [])
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.post("/stock/add",
                       data={"product_id": 999, "quantity": 1})
    # Erreur métier : redirection vers la liste, le flash y sera affiché
    assert resp.status_code == 302
    assert "/stock" in resp.headers["Location"]
    with SessionLocal() as s:
        count = s.query(Stock).filter_by(product_id=999).count()
        assert count == 0
    # Le flash d'erreur ("... inconnu de l'API") est remonté à destination
    suite = client.get("/stock", follow_redirects=False)
    assert "inconnu".encode() in suite.data
