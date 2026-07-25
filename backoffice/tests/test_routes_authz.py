"""Tests d'autorisation : chaque rôle reste dans son périmètre."""

ADMIN_PASSWORD = "admin-pass"
EMPLOYEE_PASSWORD = "bob-pass"


def test_employe_interdit_sur_users(client, employee, login):
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.get("/users")
    assert resp.status_code == 403


def test_admin_interdit_sur_stock(client, admin, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.get("/stock")
    assert resp.status_code == 403


def test_users_exige_connexion(client):
    resp = client.get("/users")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_stock_exige_connexion(client):
    resp = client.get("/stock")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_suppression_user_exige_admin(client, employee, login):
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.post(f"/users/{employee.id}/delete")
    assert resp.status_code == 403


def test_admin_voit_la_liste_users(client, admin, employee, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.get("/users")
    assert resp.status_code == 200
    assert b"bob" in resp.data


def test_stock_degrade_si_api_indisponible(
        client, employee, login, monkeypatch):
    import views.stock as stock_view
    from services.errors import ProductApiUnavailable

    def boom():
        raise ProductApiUnavailable("API down")

    monkeypatch.setattr(stock_view, "list_products", boom)
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.get("/stock")
    assert resp.status_code == 200
    assert "indisponible".encode() in resp.data


def test_employe_voit_son_stock(client, employee, login, session, monkeypatch):
    import views.stock as stock_view
    from models import Stock
    monkeypatch.setattr(
        stock_view, "list_products",
        lambda: [{"id": 5, "name": "Widget",
                  "unit_price": 10.0, "description": "d"}],
    )
    session.add(Stock(branch_id=employee.branch_id, product_id=5, quantity=3))
    session.commit()
    login("bob", EMPLOYEE_PASSWORD)
    resp = client.get("/stock")
    assert resp.status_code == 200
    assert b"Widget" in resp.data
