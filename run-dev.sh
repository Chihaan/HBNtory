#!/usr/bin/env bash
#
# Lance l'environnement de dev du Backoffice.
#   - base PostgreSQL + API produits dans Docker
#   - Flask en local (venv), branché sur la base via localhost
#
# Usage : ./run-dev.sh
#
set -e

# Se placer à la racine du projet (là où est ce script).
cd "$(dirname "$0")"

# 1. Base + API produits dans Docker (attend qu'elles soient prêtes).
docker compose up -d --wait db external-products-api

# 2. Environnement Python local.
source .venv/bin/activate

# 3. Variables : on charge le .env, MAIS Flask tourne sur l'hôte,
#    donc la base est joignable en localhost, pas via le nom "db".
set -a
source .env
set +a
export DATABASE_URL="${DATABASE_URL/@db:/@localhost:}"
export FLASK_APP="app:create_app"

# 4. Lancer le serveur de dev depuis le dossier backoffice.
cd backoffice
python -m flask run --debug
