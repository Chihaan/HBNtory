"""Tests end-to-end du JS réellement exécuté dans le navigateur."""

ADMIN_PASSWORD = "admin-pass"


def _login(page, base_url):
    page.goto(base_url + "/login")
    page.fill("input[name=username]", "admin")
    page.fill("input[name=password]", ADMIN_PASSWORD)
    page.click("button[type=submit]")


def test_connexion_aboutit_sur_users(page, base_url):
    """Le cycle de connexion complet mène à la page Utilisateurs."""
    _login(page, base_url)
    page.wait_for_url("**/users")
    assert "Utilisateurs" in page.content()


def test_oeil_affiche_le_mot_de_passe(page, base_url):
    """Le bouton œil bascule le champ mot de passe en clair."""
    page.goto(base_url + "/login")
    champ = page.locator("#login-pw")
    assert champ.get_attribute("type") == "password"
    page.click(".pw-toggle")
    assert champ.get_attribute("type") == "text"


def test_modale_nouvel_employe_s_ouvre(page, base_url):
    """Le bouton 'Ajouter un employé' ouvre la modale (dialog)."""
    _login(page, base_url)
    page.wait_for_url("**/users")
    assert not page.locator("#dlg-new").is_visible()
    page.click("#add-user-btn")
    assert page.locator("#dlg-new").is_visible()


def test_confirmation_mot_de_passe_bloque_si_different(page, base_url):
    """Deux mots de passe différents empêchent la soumission."""
    _login(page, base_url)
    page.wait_for_url("**/users")
    # Ouvre la modale mot de passe du 1er employé listé.
    # Dans un tableau court le menu s'ouvre vers le haut et chevauche le
    # hero, qui intercepte le clic « géométrique ». On déclenche donc le
    # handler directement sur l'élément (sans test de superposition).
    page.click("details.actions summary")
    page.locator("button[data-pw]").dispatch_event("click")
    page.wait_for_selector("#pw1", state="visible")
    page.fill("#pw1", "aaa")
    page.fill("#pw2", "bbb")
    page.click("#dlg-pw button[type=submit]")
    # La modale reste ouverte et l'erreur s'affiche
    assert page.locator("#pw-error").is_visible()
