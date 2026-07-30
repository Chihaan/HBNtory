"""Vérifie que les délais des trois couches restent cohérents.

Aucun appel à Groq : on teste les constantes, la coupure du budget
global et le code HTTP renvoyé au client web.
"""

import asyncio
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent
import app as app_module

CWI = Path(__file__).resolve().parents[2] / "client-web-interface"

client = TestClient(app_module.app)


def _nginx_timeout(directive):
    """Lit un `proxy_*_timeout` de nginx.conf, en secondes."""
    configuration = (CWI / "nginx.conf").read_text(encoding="utf-8")
    found = re.search(rf"{directive}\s+(\d+)s\s*;", configuration)
    assert found, f"{directive} absent de nginx.conf"
    return int(found.group(1))


def _browser_timeout_seconds():
    """Lit le délai de l'AbortController de script.js, en secondes."""
    script = (CWI / "script.js").read_text(encoding="utf-8")
    found = re.search(r"REQUEST_TIMEOUT_MS\s*=\s*(\d+)", script)
    assert found, "REQUEST_TIMEOUT_MS absent de script.js"
    return int(found.group(1)) / 1000


@pytest.mark.skipif(not CWI.exists(), reason="client-web-interface absent")
def test_les_delais_sont_croissants_du_plus_interne_au_plus_externe():
    """AI Service < Nginx < navigateur : l'interne coupe en premier."""
    nginx_read = _nginx_timeout("proxy_read_timeout")

    assert agent.REQUEST_BUDGET_SECONDS < nginx_read
    assert nginx_read <= _browser_timeout_seconds()
    assert _nginx_timeout("proxy_connect_timeout") < nginx_read
    assert _nginx_timeout("proxy_send_timeout") == nginx_read


def test_un_tour_d_outil_complet_tient_dans_le_budget():
    """Le budget laisse la place à au moins un aller-retour LLM + MCP."""
    un_tour = agent.LLM_TIMEOUT_SECONDS + agent.MCP_TIMEOUT_SECONDS

    assert un_tour < agent.REQUEST_BUDGET_SECONDS
    assert agent.MAX_TOOL_ROUNDS >= 2


def test_la_boucle_d_outils_ne_peut_pas_durer_plusieurs_minutes(monkeypatch):
    """Même si le LLM boucle sans fin, ask_agent est coupé net."""
    async def boucle_sans_fin(question, question_id):
        await asyncio.sleep(30)
        return "jamais atteint"

    monkeypatch.setattr(agent, "_ask_agent", boucle_sans_fin)
    monkeypatch.setattr(agent, "REQUEST_BUDGET_SECONDS", 0.05)

    with pytest.raises(agent.AgentTimeoutError) as leve:
        asyncio.run(agent.ask_agent("Une question quelconque ?"))

    assert "trop de temps" in str(leve.value)


def test_le_depassement_de_budget_donne_un_504_en_francais(monkeypatch):
    async def trop_lent(question):
        raise agent.AgentTimeoutError("trop long")

    monkeypatch.setattr(app_module, "ask_agent", trop_lent)
    response = client.post("/ask", json={"question": "Où est le produit 1 ?"})

    assert response.status_code == 504
    assert "trop de temps" in response.json()["detail"]
