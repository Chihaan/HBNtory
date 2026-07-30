"""Vérifie le flux navigateur -> Nginx -> AI Service, sans Groq.

Le trajet complet ne peut être joué qu'avec la stack démarrée
(`./smoke-test.sh`). Ces tests contrôlent ce qui casse le plus souvent
et qui est vérifiable hors Docker : le contrat entre les trois couches.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

import app as app_module

RACINE = Path(__file__).resolve().parents[2]
CWI = RACINE / "client-web-interface"

client = TestClient(app_module.app)

pytestmark = pytest.mark.skipif(
    not CWI.exists(), reason="client-web-interface absent"
)


def _proxy_pass():
    """Retourne l'URL amont configurée pour `location /api/`."""
    configuration = (CWI / "nginx.conf").read_text(encoding="utf-8")
    bloc = re.search(r"location\s+/api/\s*\{(.*?)\n\s*\}", configuration,
                     re.DOTALL)
    assert bloc, "location /api/ absent de nginx.conf"
    cible = re.search(r"proxy_pass\s+(\S+?)\s*;", bloc.group(1))
    assert cible, "proxy_pass absent du bloc /api/"
    return cible.group(1)


def _chemin_transmis(chemin_demande):
    """Reproduit la réécriture faite par Nginx pour `location /api/`."""
    amont = urlsplit(_proxy_pass())
    assert amont.path, (
        "proxy_pass doit se terminer par un / : sans chemin, Nginx "
        "transmet /api/ask tel quel et l'AI Service répond 404."
    )
    return amont.path + chemin_demande.removeprefix("/api/")


def test_le_client_web_poste_du_json_sur_api_ask():
    """Premier saut : ce que le navigateur envoie réellement."""
    script = (CWI / "script.js").read_text(encoding="utf-8")

    assert 'fetch("/api/ask"' in script
    assert 'method: "POST"' in script
    assert '"Content-Type": "application/json"' in script
    assert "JSON.stringify({question})" in script


def test_nginx_transforme_api_ask_en_ask():
    """Deuxième saut : le préfixe /api est retiré avant l'AI Service."""
    assert _chemin_transmis("/api/ask") == "/ask"
    assert _chemin_transmis("/api/health") == "/health"


def test_le_proxy_vise_le_service_ai_de_docker_compose():
    """Le nom DNS et le port du proxy existent bien dans la stack."""
    amont = urlsplit(_proxy_pass())
    compose = (RACINE / "docker-compose.yml").read_text(encoding="utf-8")

    assert f"\n  {amont.hostname}:\n" in compose, (
        f"{amont.hostname} n'est pas un service de docker-compose.yml"
    )
    assert f'"{amont.port}:{amont.port}"' in compose


def test_l_ai_service_repond_au_corps_envoye_par_le_navigateur(monkeypatch):
    """Troisième saut : le corps du navigateur est accepté tel quel."""
    async def fake_ask(question):
        assert question == "Où trouver trois ordinateurs portables ?"
        return "À Fréjus Centre."

    monkeypatch.setattr(app_module, "ask_agent", fake_ask)
    reponse = client.post(
        _chemin_transmis("/api/ask"),
        headers={"Content-Type": "application/json"},
        content=b'{"question":"O\xc3\xb9 trouver trois ordinateurs '
                b'portables ?"}',
    )

    assert reponse.status_code == 200
    assert reponse.json() == {"answer": "À Fréjus Centre."}
    assert "data.answer" in (CWI / "script.js").read_text(encoding="utf-8")


def test_le_smoke_test_attend_ce_que_l_ai_service_renvoie_vraiment():
    """Le contrôle du smoke test reste valide si les règles changent.

    `smoke-test.sh` prouve que le corps JSON a bien traversé Nginx en
    envoyant 1001 caractères et en cherchant `string_too_long` dans la
    réponse. Ce test échoue si l'AI Service cesse de produire ce motif.
    """
    script = (RACINE / "smoke-test.sh").read_text(encoding="utf-8")
    longueur = re.search(r"^LONGUEUR_ENVOYEE=(\d+)$", script, re.MULTILINE)
    erreur = re.search(r"^ERREUR_ATTENDUE=(\w+)$", script, re.MULTILINE)
    assert longueur and erreur, "constantes absentes de smoke-test.sh"

    reponse = client.post(
        "/ask", json={"question": "a" * int(longueur[1])}
    )

    assert reponse.status_code == 422
    assert reponse.json()["detail"][0]["type"] == erreur[1]
