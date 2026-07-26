#!/usr/bin/env bash

set -Eeuo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

DEV_PYTHON=".venv/bin/python"

# --------------------------------------------------
# 1. Vérifications
# --------------------------------------------------

if [[ ! -f ".env" ]]; then
    echo "Erreur : fichier .env absent."
    echo "Crée-le avec : cp .env.exemple .env"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Erreur : Docker n'est pas installé."
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Erreur : le plugin Docker Compose est introuvable."
    echo "Installe Docker Desktop ou Docker Compose v2."
    exit 1
fi

COMPOSE_UP_HELP="$(docker compose up --help 2>&1 || true)"
if [[ "$COMPOSE_UP_HELP" != *"--wait"* ]]; then
    echo "Erreur : cette version de Docker Compose ne supporte pas --wait."
    echo "Mets Docker Desktop ou Docker Compose à jour."
    exit 1
fi

# --------------------------------------------------
# 2. Démarrer OrbStack si Docker est arrêté
# --------------------------------------------------

if ! docker info >/dev/null 2>&1; then
    if command -v orbctl >/dev/null 2>&1; then
        echo "Démarrage d'OrbStack..."
        orbctl start
    else
        echo "Erreur : le moteur Docker est arrêté."
        echo "Démarre Docker Desktop ou le service Docker, puis réessaie."
        exit 1
    fi

    echo "Attente du moteur Docker..."

    for _ in {1..30}; do
        if docker info >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    if ! docker info >/dev/null 2>&1; then
        echo "Erreur : Docker n'est pas disponible après 30 secondes."
        exit 1
    fi
fi

echo "Docker est prêt."

# --------------------------------------------------
# 3. Préparer l'environnement Python
# --------------------------------------------------

python_is_supported() {
    "$1" -c \
        'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' \
        >/dev/null 2>&1
}

if [[ ! -x "$DEV_PYTHON" ]]; then
    PYTHON_BIN="python3"
    if command -v python3.12 >/dev/null 2>&1; then
        PYTHON_BIN="python3.12"
    fi

    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        echo "Erreur : Python 3.12 est requis."
        exit 1
    fi
    if ! python_is_supported "$PYTHON_BIN"; then
        echo "Erreur : Python 3.12 est requis par les dépendances du projet."
        echo "Version détectée : $("$PYTHON_BIN" --version 2>&1)"
        exit 1
    fi

    echo "Création de l'environnement virtuel..."
    "$PYTHON_BIN" -m venv .venv
elif ! python_is_supported "$DEV_PYTHON"; then
    echo "Erreur : le venv existant n'utilise pas Python 3.12."
    echo "Version détectée : $("$DEV_PYTHON" --version 2>&1)"
    echo "Recrée-le avec : python3.12 -m venv --clear .venv"
    exit 1
fi

echo "Vérification des dépendances Python..."
"$DEV_PYTHON" -m pip install \
    --disable-pip-version-check \
    -r backoffice/requirements.txt

# --------------------------------------------------
# 4. Démarrer PostgreSQL et l'API produits
# --------------------------------------------------

echo "Démarrage de PostgreSQL et de l'API produits..."

docker compose up -d --wait db external-products-api

# --------------------------------------------------
# 5. Charger et adapter les variables d'environnement
# --------------------------------------------------

set -a
source .env
set +a

# Flask tourne sur l'hôte (macOS, Linux ou WSL), hors du réseau Docker.
export DATABASE_URL="${DATABASE_URL/@db:/@127.0.0.1:}"
export PRODUCTS_API_URL="http://127.0.0.1:5001"
export FLASK_APP="app:create_app"

# --------------------------------------------------
# 6. Initialiser la base
# --------------------------------------------------

cd backoffice

echo "Initialisation des tables, permissions et données..."
"../$DEV_PYTHON" bootstrap.py

# --------------------------------------------------
# 7. Démarrer Flask
# --------------------------------------------------

echo
echo "Backoffice : http://127.0.0.1:8000"
echo "API produits : http://127.0.0.1:5001"
echo "Arrêt de Flask : Ctrl+C"
echo

exec "../$DEV_PYTHON" -m flask run \
    --debug \
    --host 127.0.0.1 \
    --port 8000
