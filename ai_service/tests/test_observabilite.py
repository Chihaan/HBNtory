"""Vérifie la traçabilité des appels MCP, sans Groq ni Docker.

Le journal est le seul outil de diagnostic pendant une démonstration :
il doit dire quel outil MCP a été appelé, s'il a réussi et en combien
de temps, sans jamais recopier la question posée, la réponse produite
ni la clé d'API.
"""

import asyncio
import logging
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import agent

CLE_FACTICE = "cle-groq-de-test-jamais-journalisee"
QUESTION = "Où trouver trois ordinateurs portables ?"
REPONSE = "Trois unités sont disponibles à Fréjus Centre."
OUTIL = "stock_get_stock_by_product"

# Un outil MCP peut renvoyer n'importe quoi dans son champ "error" :
# une chaîne de connexion complète en fait partie.
SECRET_DANS_ERREUR = "postgresql://hbntory:motdepasse@db:5432/hbntory"


class FauxMCP:
    """Client MCP minimal, dont on choisit la réponse ou la panne."""

    def __init__(self, donnees=None, panne=None):
        self.donnees = donnees or {"success": True, "branches": []}
        self.panne = panne

    async def __aenter__(self):
        return self

    async def __aexit__(self, *informations):
        return False

    async def list_tools(self):
        return [SimpleNamespace(
            name=OUTIL,
            description="Stock d'un produit.",
            inputSchema={"type": "object", "properties": {}},
        )]

    async def call_tool(self, name, arguments, timeout):
        if self.panne is not None:
            raise self.panne
        return SimpleNamespace(data=self.donnees)


class FauxLLM:
    """Client Groq minimal : demande l'outil, puis répond.

    Il est construit par le vrai `build_llm_client`, donc avec la clé
    d'API lue dans l'environnement : ce chemin est bien celui que les
    tests inspectent quand ils vérifient qu'aucun secret ne fuit.
    """

    def __init__(self, **parametres):
        self.parametres = parametres
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        appel = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(
                name=OUTIL,
                arguments='{"product_id": 1}',
            ),
        )
        self._messages = [
            SimpleNamespace(content=None, tool_calls=[appel]),
            SimpleNamespace(content=REPONSE, tool_calls=None),
        ]

    async def _create(self, **parametres):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=self._messages.pop(0))]
        )

    async def close(self):
        return None


class LLMSansOutil(FauxLLM):
    """Répond sans utiliser d'outil, ce que l'agent refuse."""

    def __init__(self, **parametres):
        super().__init__(**parametres)
        self._messages = [
            SimpleNamespace(content=REPONSE, tool_calls=None),
        ]


@pytest.fixture
def poser_question(monkeypatch):
    """Pose une question au vrai agent, Groq et MCP étant doublés."""
    monkeypatch.setenv("GROQ_API_KEY", CLE_FACTICE)

    def _poser(mcp=None, llm=FauxLLM):
        double = mcp or FauxMCP()
        monkeypatch.setattr(agent, "AsyncOpenAI", llm)
        monkeypatch.setattr(agent, "build_mcp_client", lambda: double)
        return asyncio.run(agent.ask_agent(QUESTION))

    return _poser


def _enregistrements_outil(caplog):
    """Lignes de journal décrivant un appel d'outil MCP."""
    return [
        enregistrement
        for enregistrement in caplog.records
        if " outil " in enregistrement.getMessage()
    ]


def _identifiants(caplog):
    """Identifiants de question trouvés en tête des lignes de journal."""
    identifiants = set()
    for message in caplog.messages:
        trouve = re.match(r"\[([0-9a-f]{8})\] ", message)
        if trouve:
            identifiants.add(trouve.group(1))
    return identifiants


def test_un_appel_d_outil_reussi_est_journalise(poser_question, caplog):
    """Quel outil, quelle issue, quelle durée : les trois sont tracés."""
    with caplog.at_level(logging.INFO, logger="agent"):
        reponse = poser_question()

    assert reponse == REPONSE
    (enregistrement,) = _enregistrements_outil(caplog)
    assert enregistrement.levelno == logging.INFO
    assert OUTIL in enregistrement.getMessage()
    assert "succès" in enregistrement.getMessage()
    assert re.search(r"en \d+ ms", enregistrement.getMessage())


def test_un_outil_injoignable_est_journalise_avec_sa_cause(
        poser_question, caplog):
    """Une panne d'un serveur MCP doit sauter aux yeux dans le journal.

    L'agent, lui, continue : l'appel raté devient un message d'erreur
    transmis au modèle. Sans cette ligne, cette panne serait invisible.
    """
    with caplog.at_level(logging.INFO, logger="agent"):
        poser_question(FauxMCP(panne=TimeoutError()))

    (enregistrement,) = _enregistrements_outil(caplog)
    assert enregistrement.levelno == logging.WARNING
    assert "échec" in enregistrement.getMessage()
    assert "TimeoutError" in enregistrement.getMessage()


def test_un_outil_qui_signale_une_panne_n_est_pas_dit_reussi(
        poser_question, caplog):
    """Les outils du projet ne lèvent pas d'exception.

    Ils répondent `{"success": false, "error": "..."}`. L'appel MCP a
    donc techniquement réussi, alors que la donnée demandée n'a pas pu
    être lue : le journal doit rapporter l'échec, pas le succès.

    Le constat suffit : le message d'erreur est du contenu renvoyé par
    l'outil, et rien ne garantit ce qu'il transporte.
    """
    panne = {
        "success": False,
        "error": f"Impossible de se connecter a {SECRET_DANS_ERREUR}.",
    }
    with caplog.at_level(logging.INFO, logger="agent"):
        poser_question(FauxMCP(donnees=panne))

    (enregistrement,) = _enregistrements_outil(caplog)
    assert enregistrement.levelno == logging.WARNING
    assert "échec" in enregistrement.getMessage()
    assert "erreur signalée par l'outil" in enregistrement.getMessage()
    assert SECRET_DANS_ERREUR not in "\n".join(caplog.messages)


def test_le_journal_ne_recopie_ni_la_question_ni_la_reponse_ni_la_cle(
        poser_question, caplog):
    """Un journal n'est pas un endroit où stocker des données.

    La taille de la question suffit à diagnostiquer un corps tronqué ;
    son contenu, la réponse et la clé d'API n'ont rien à y faire.
    """
    with caplog.at_level(logging.INFO, logger="agent"):
        poser_question()

    journal = "\n".join(caplog.messages)
    assert QUESTION not in journal
    assert REPONSE not in journal
    assert CLE_FACTICE not in journal
    assert f"{len(QUESTION)} caractères" in journal


def test_la_duree_totale_de_la_question_est_journalisee(
        poser_question, caplog):
    """Comparer cette durée à celle des outils situe la lenteur."""
    with caplog.at_level(logging.INFO, logger="agent"):
        poser_question()

    journal = "\n".join(caplog.messages)
    assert re.search(r"réponse produite en \d+ ms", journal)


def test_une_question_en_echec_laisse_une_trace_avec_sa_raison(
        poser_question, caplog):
    """Le client web ne reçoit qu'un message générique (503).

    La raison réelle doit donc rester lisible côté serveur, rattachée à
    l'identifiant de la question concernée.
    """
    with caplog.at_level(logging.INFO, logger="agent"):
        with pytest.raises(agent.AgentServiceError):
            poser_question(llm=LLMSansOutil)

    dernier = caplog.records[-1]
    assert dernier.levelno == logging.WARNING
    assert "échec après" in dernier.getMessage()
    assert "aucun outil" in dernier.getMessage()


def test_les_lignes_d_une_meme_question_partagent_un_identifiant(
        poser_question, caplog):
    """Deux questions simultanées restent distinguables dans le journal."""
    with caplog.at_level(logging.INFO, logger="agent"):
        poser_question()
        premiere_question = _identifiants(caplog)
        poser_question()

    assert len(premiere_question) == 1
    assert len(_identifiants(caplog)) == 2


def test_nos_lignes_sortent_du_conteneur_mais_pas_celles_des_librairies():
    """Vérifie la configuration réelle des journaux, hors pytest.

    Un logger Python n'émet rien sous WARNING tant que personne ne l'a
    configuré, et Uvicorn ne configure que ses propres journaux : sans
    l'appel de `app.py`, toutes les lignes ci-dessus existeraient dans
    le code sans jamais apparaître dans `docker compose logs`. À
    l'inverse, tout passer en INFO ferait remonter une ligne par requête
    HTTP de httpx et du protocole MCP, entre les nôtres. pytest
    installant ses propres gestionnaires, la vérification n'a de sens
    que dans un processus neuf.
    """
    programme = (
        "import logging, app, agent; "
        "agent.logger.info('ligne-a-garder'); "
        "logging.getLogger('httpx').info('bruit-a-taire')"
    )
    execution = subprocess.run(
        [sys.executable, "-c", programme],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert execution.returncode == 0, execution.stderr
    assert "ligne-a-garder" in execution.stderr
    assert "bruit-a-taire" not in execution.stderr
