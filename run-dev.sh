#!/usr/bin/env bash

set -Eeuo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ ! -f ".env" ]]; then
    echo "Erreur : fichier .env absent."
    echo "Crée-le puis complète-le avec :"
    echo "  cp .env.exemple .env"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Erreur : la commande docker est introuvable."
    echo "Installe Docker Desktop et active son intégration avec ton terminal."
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Erreur : Docker Compose v2 est introuvable."
    echo "Installe ou mets à jour Docker Desktop."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    if [[ "$(uname -s)" == "Darwin" ]] &&
       command -v open >/dev/null 2>&1; then
        echo "Démarrage de Docker Desktop..."
        open -a Docker

        echo "Attente du moteur Docker..."
        for _ in {1..30}; do
            if docker info >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
    fi

    if ! docker info >/dev/null 2>&1; then
        echo "Erreur : le moteur Docker n'est pas disponible."
        echo "Démarre Docker Desktop puis relance ce script."
        echo "Sous WSL, active aussi Settings > Resources > WSL Integration."
        exit 1
    fi
fi

if ! docker compose config --quiet; then
    echo "Erreur : docker-compose.yml ou .env contient une erreur."
    exit 1
fi

if ! grep -Eq '^GEMINI_API_KEY=.+$' .env; then
    echo "Attention : GEMINI_API_KEY est vide ou absente dans .env."
    echo "La stack démarrera, mais l'assistant IA ne pourra pas répondre."
    echo
fi

echo "Démarrage de la stack HBNtory..."
echo
echo "Client web   : http://127.0.0.1:8080"
echo "Backoffice   : http://127.0.0.1:8000"
echo "AI Service   : http://127.0.0.1:8002"
echo "API produits : http://127.0.0.1:5001"
echo
echo "Utilise Ctrl+C pour arrêter la stack."
echo

exec docker compose up --build
