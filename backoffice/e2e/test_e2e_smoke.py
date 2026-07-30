"""Tests end-to-end du JS réellement exécuté dans le navigateur."""

from datetime import datetime


ADMIN_PASSWORD = "admin-pass"


def _login(page, base_url):
    page.goto(base_url + "/login")
    page.fill("input[name=username]", "admin")
    page.fill("input[name=password]", ADMIN_PASSWORD)
    page.click("button[type=submit]")


def _login_employee(page, base_url):
    page.goto(base_url + "/login")
    page.fill("input[name=username]", "bob")
    page.fill("input[name=password]", "bob-pass")
    page.click("button[type=submit]")
    page.wait_for_url("**/stock")


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
    page.fill("#pw1", "password-a")
    page.fill("#pw2", "password-b")
    page.click("#dlg-pw button[type=submit]")
    # La modale reste ouverte et l'erreur s'affiche
    assert page.locator("#pw-error").is_visible()


def test_filtres_stock_et_reinitialisation(page, base_url):
    """Les filtres catégorie/état se combinent et peuvent être effacés."""
    _login_employee(page, base_url)
    rows = page.locator("tr.prod-row")
    assert rows.count() == 2

    page.click("#cat-combo .combo-trigger")
    page.click('#cat-combo .combo-option[data-id="Écrans"]')
    assert page.locator("tr.prod-row:visible").count() == 1

    page.click("#state-combo .combo-trigger")
    page.click('#state-combo .combo-option[data-id="1"]')
    assert page.locator("tr.prod-row:visible").count() == 0
    assert page.locator("#empty-row").is_visible()
    assert "0 produits sur 2" in page.locator("#results-count").inner_text()

    page.click("#filter-reset")
    assert page.locator("tr.prod-row:visible").count() == 2
    assert "2 produits sur 2" in page.locator("#results-count").inner_text()


def test_carte_en_rupture_filtre_le_tableau(page, base_url):
    """La carte KPI applique et retire le filtre des ruptures."""
    _login_employee(page, base_url)
    card = page.locator("#out-of-stock-card")

    card.click()
    assert card.get_attribute("aria-pressed") == "true"
    assert page.locator("tr.prod-row:visible").count() == 1
    assert page.locator('tr.prod-row[data-id="2"]').is_visible()

    card.click()
    assert card.get_attribute("aria-pressed") == "false"
    assert page.locator("tr.prod-row:visible").count() == 2


def test_un_seul_filtre_deroulant_est_ouvert(page, base_url):
    """Ouvrir un filtre referme le filtre qui était déjà déployé."""
    _login_employee(page, base_url)

    page.click("#cat-combo .combo-trigger")
    assert page.locator("#cat-combo .combo-panel").is_visible()
    page.click("#state-combo .combo-trigger")

    assert not page.locator("#cat-combo .combo-panel").is_visible()
    assert page.locator("#state-combo .combo-panel").is_visible()


def test_tri_active_la_reinitialisation(page, base_url):
    """Le bouton de remise à zéro annule aussi le tri du tableau."""
    _login_employee(page, base_url)
    reset = page.locator("#filter-reset")
    id_header = page.locator('th[data-key="id"]')

    assert reset.is_disabled()
    id_header.click()
    assert reset.is_enabled()
    assert id_header.get_attribute("aria-sort") == "descending"
    assert page.locator("tr.prod-row").first.get_attribute("data-id") == "2"

    reset.click()
    assert reset.is_disabled()
    assert id_header.get_attribute("aria-sort") == "none"
    assert page.locator("tr.prod-row").first.get_attribute("data-id") == "1"


def test_recherche_stock_par_sku_et_message_accueil(page, base_url):
    """Le SKU est visible/recherchable et l'accueil suit l'heure locale."""
    page.clock.install(time=datetime(2026, 7, 26, 18, 0))
    _login_employee(page, base_url)

    assert page.locator("#page-greeting").inner_text() == "Bonsoir bob !"
    assert page.locator('tr[data-id="1"] .sku').inner_text() == "HB-LAP-1001"
    page.fill("#search", "HB-MON-2101")
    assert page.locator("tr.prod-row:visible").count() == 1
    assert page.locator('tr.prod-row[data-id="2"]').is_visible()


def test_detail_produit_accessible_au_clavier(page, base_url):
    """Entrée sur une ligne ouvre le détail sans utiliser la souris."""
    _login_employee(page, base_url)
    row = page.locator('tr.prod-row[data-id="1"]')
    row.focus()
    page.keyboard.press("Enter")
    assert page.locator("#dlg-detail").is_visible()
    assert "Ordinateur étudiant" in page.locator("#d-name").inner_text()


def test_detail_produit_permet_ajout_et_retrait(page, base_url):
    """La fiche produit donne accès aux deux mouvements de stock."""
    _login_employee(page, base_url)
    row = page.locator('tr.prod-row[data-id="1"]')
    row_image = row.locator(".thumb img")

    assert row_image.get_attribute("src").endswith(
        "/static/images/products/HB-LAP-1001.png"
    )
    assert row_image.evaluate(
        "(image) => image.complete && image.naturalWidth > 0"
    )

    row.click()
    assert page.locator("#d-sku").inner_text() == "SKU HB-LAP-1001"
    detail_image = page.locator("#d-image")
    assert detail_image.is_visible()
    assert detail_image.get_attribute("src").endswith(
        "/static/images/products/HB-LAP-1001.png"
    )
    assert detail_image.get_attribute("alt") == (
        "Image de Ordinateur étudiant"
    )
    assert detail_image.evaluate(
        "(image) => image.complete && image.naturalWidth > 0"
    )
    page.click("#d-add")
    assert not page.locator("#dlg-detail").is_visible()
    assert page.locator("#dlg-add").is_visible()
    assert page.locator("#combo-add .combo-value").input_value() == "1"
    page.click("#dlg-add [data-close]")

    row.click()
    page.click("#d-remove")
    assert not page.locator("#dlg-detail").is_visible()
    assert page.locator("#dlg-remove").is_visible()
    assert page.locator("#remove-product-id").input_value() == "1"
    assert (
        page.locator("#remove-product-label").input_value()
        == "HB-LAP-1001 · Ordinateur étudiant"
    )


def test_stock_reste_utilisable_sur_mobile(page, base_url):
    """La page défile en hauteur et le tableau seulement en largeur."""
    page.set_viewport_size({"width": 390, "height": 844})
    _login_employee(page, base_url)

    assert page.evaluate(
        "document.body.scrollWidth <= window.innerWidth"
    )
    assert page.locator(".table-scroll").evaluate(
        "(el) => getComputedStyle(el).maxHeight"
    ) == "none"
    dimensions = page.locator(".table-scroll").evaluate(
        "(el) => ({client: el.clientWidth, scroll: el.scrollWidth})"
    )
    assert dimensions["scroll"] > dimensions["client"]
    assert page.locator("#add-product-btn").is_visible()
