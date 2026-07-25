"""Tests d'intégration de l'authentification (client Flask)."""

# Mots de passe définis dans conftest.py
ADMIN_PASSWORD = "admin-pass"
EMPLOYEE_PASSWORD = "bob-pass"


def test_page_login_accessible(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_admin_atterrit_sur_users(client, admin, login):
    # Le login renvoie vers le dashboard "/", qui aiguille par rôle
    resp = login("admin", ADMIN_PASSWORD)
    assert resp.status_code == 302
    assert resp.headers["Location"] in ("/", "http://localhost/")
    suite = client.get("/")
    assert suite.status_code == 302
    assert "/users" in suite.headers["Location"]


def test_login_employe_atterrit_sur_stock(client, employee, login):
    resp = login("bob", EMPLOYEE_PASSWORD)
    assert resp.status_code == 302
    suite = client.get("/")
    assert suite.status_code == 302
    assert "/stock" in suite.headers["Location"]


def test_login_mauvais_mot_de_passe(client, employee, login):
    resp = login("bob", "mauvais")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_utilisateur_inconnu(client, login):
    resp = login("fantome", "peu-importe")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_utilisateur_supprime_refuse(client, employee, session, login):
    from services.users import soft_delete_user
    soft_delete_user(session, employee.id)
    session.commit()
    resp = login("bob", EMPLOYEE_PASSWORD)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_utilisateur_inactif_refuse(client, employee, session, login):
    from services.users import set_active
    set_active(session, employee.id, False)
    session.commit()
    resp = login("bob", EMPLOYEE_PASSWORD)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_dashboard_non_connecte_redirige(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_non_connecte_redirige(client):
    resp = client.post("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_apres_connexion(client, admin, login):
    login("admin", ADMIN_PASSWORD)
    resp = client.post("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
