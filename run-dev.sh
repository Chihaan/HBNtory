#!/usr/bin/env bash

set -Eeuo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

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

if ! docker info >/dev/null 2>&1; then
    if [[ "$(uname -s)" == "Darwin" ]] &&
       command -v open >/dev/null 2>&1; then
        echo "Démarrage de Docker Desktop..."
        open -a Docker
    else
        echo "Erreur : le moteur Docker est arrêté."
        echo "Démarre Docker Desktop, puis réessaie."
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

if ! grep -Eq '^GROQ_API_KEY=.+$' .env; then
    echo "Attention : GROQ_API_KEY est vide ou absente dans .env."
    echo "La stack démarrera, mais les questions IA retourneront une erreur."
    echo
fi

echo "Démarrage de HBNtory..."
echo
echo "Client web  : http://127.0.0.1:8080"
echo "Backoffice  : http://127.0.0.1:8000"
echo "AI Service  : http://127.0.0.1:8002"
echo "API produits: http://127.0.0.1:5001"
echo
echo "Arrêt de la stack : Ctrl+C"
echo

exec docker compose up --build
