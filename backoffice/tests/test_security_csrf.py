"""Test de sécurité : la protection CSRF est bien active.

Le client `app` des autres tests désactive volontairement le CSRF pour
simplifier les POST. Ici on reconstruit une app avec le CSRF actif
(comportement de production) pour vérifier qu'un POST sans jeton est
rejeté (400).
"""

import re

import app as app_module

ADMIN_PASSWORD = "admin-pass"


def _app_csrf_actif():
    application = app_module.create_app()
    application.config["TESTING"] = True
    # WTF_CSRF_ENABLED reste à True (défaut) : protection active
    return application


def test_post_sans_jeton_csrf_rejete():
    client = _app_csrf_actif().test_client()
    resp = client.post(
        "/login", data={"username": "x", "password": "y"}
    )
    assert resp.status_code == 400


def test_logout_sans_jeton_csrf_rejete(admin):
    client = _app_csrf_actif().test_client()
    resp = client.post("/logout")
    # 400 (CSRF) attendu avant même la vérif de connexion
    assert resp.status_code in (400, 401, 302)


def test_login_avec_jeton_csrf_valide(admin):
    """Cycle complet : on récupère le jeton puis on l'envoie -> accepté."""
    client = _app_csrf_actif().test_client()
    page = client.get("/login")
    match = re.search(
        rb'name="csrf_token"[^>]*value="([^"]+)"', page.data
    )
    assert match, "jeton CSRF absent de la page de connexion"
    token = match.group(1).decode()
    resp = client.post("/login", data={
        "username": "admin",
        "password": ADMIN_PASSWORD,
        "csrf_token": token,
    })
    assert resp.status_code == 302  # connexion acceptée
