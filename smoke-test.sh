#!/usr/bin/env bash
#
# Smoke test du flux complet : navigateur -> Nginx -> AI Service.
#
# Ne consomme aucun quota IA : les trois vérifications s'arrêtent
# avant l'appel au modèle (route /health, puis question volontairement
# invalide, rejetée par la validation FastAPI avant l'agent).
#
# Prérequis : la stack tourne déjà (./run-dev.sh dans un autre terminal).
#
# Usage :
#   ./smoke-test.sh                 # les 3 étapes, sans Groq
#   ./smoke-test.sh --avec-ia       # + une vraie question (consomme du quota)
#   BASE_URL=http://127.0.0.1:8080 ./smoke-test.sh

set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
AVEC_IA=0
if [[ "${1:-}" == "--avec-ia" ]]; then
    AVEC_IA=1
fi

CORPS="$(mktemp)"
trap 'rm -f "$CORPS"' EXIT

echecs=0

titre() { printf '\n== %s\n' "$1"; }
ok() { printf '   OK    %s\n' "$1"; }
echec() { printf '   ECHEC %s\n' "$1"; echecs=$((echecs + 1)); }

# appel METHODE CHEMIN [CORPS_JSON]
# Écrit la réponse dans $CORPS et affiche le code HTTP. curl affiche
# lui-même "000" quand la connexion échoue ; `|| true` évite seulement
# que son code de sortie n'interrompe le script (set -e).
appel() {
    local methode="$1" chemin="$2"
    if [[ "$#" -ge 3 ]]; then
        curl -sS -o "$CORPS" -w '%{http_code}' \
            -X "$methode" \
            -H 'Content-Type: application/json' \
            --data "$3" \
            "$BASE_URL$chemin" 2>/dev/null || true
    else
        curl -sS -o "$CORPS" -w '%{http_code}' \
            -X "$methode" "$BASE_URL$chemin" 2>/dev/null || true
    fi
}

printf 'Cible : %s\n' "$BASE_URL"

titre "1/3 Nginx sert le client web"
code="$(appel GET /)"
if [[ "$code" == "200" ]] && grep -q 'id="query-form"' "$CORPS"; then
    ok "GET / -> 200, la page contient le formulaire"
else
    echec "GET / -> $code (la stack est-elle démarrée ? ./run-dev.sh)"
fi

titre "2/3 Nginx atteint l'AI Service et retire le préfixe /api"
code="$(appel GET /api/health)"
if [[ "$code" == "200" ]] && grep -q '"status":"ok"' "$CORPS"; then
    ok "GET /api/health -> 200 (le proxy mène bien à /health du service)"
else
    echec "GET /api/health -> $code (proxy_pass ou ai-service en cause)"
fi

titre "3/3 POST /api/ask transmet le corps JSON à POST /ask"
# Une question plus longue que la limite : la seule façon d'obtenir
# "string_too_long" est que le corps soit arrivé entier jusqu'à la
# validation FastAPI, qui rejette la question AVANT tout appel à Groq.
# Ces deux constantes sont vérifiées par
# ai_service/tests/test_flux_client_web.py.
LONGUEUR_ENVOYEE=1001
ERREUR_ATTENDUE=string_too_long

question="$(printf 'a%.0s' $(seq "$LONGUEUR_ENVOYEE"))"
code="$(appel POST /api/ask "{\"question\": \"$question\"}")"
if [[ "$code" == "422" ]] && grep -q "$ERREUR_ATTENDUE" "$CORPS"; then
    ok "corps de $LONGUEUR_ENVOYEE caractères reçu et validé (422)"
else
    echec "POST /api/ask -> $code (corps non transmis ou route absente)"
fi

if [[ "$AVEC_IA" -eq 1 ]]; then
    titre "4/4 Question réelle (consomme du quota Groq)"
    code="$(appel POST /api/ask '{"question": "Quels produits existent ?"}')"
    if [[ "$code" == "200" ]] && grep -q '"answer"' "$CORPS"; then
        ok "POST /api/ask -> 200 avec un champ answer"
        printf '   Réponse : '
        head -c 300 "$CORPS"
        printf '\n'
    else
        echec "POST /api/ask -> $code (voir les logs de ai-service)"
    fi
fi

printf '\n'
if [[ "$echecs" -eq 0 ]]; then
    printf 'Flux navigateur -> Nginx -> AI Service : OK\n'
else
    printf '%s vérification(s) en échec.\n' "$echecs"
    exit 1
fi
