# Tests manuels — Stock MCP Server

Tests executes contre une vraie base PostgreSQL (via run-dev.sh), avec
les donnees de demo generees par backoffice/seed.py (succursales
"Frejus Centre" et "Laval Gare"), et le role en lecture seule mcp_reader
cree par backoffice/init_db.py.

## Test 1 — Stock d'un produit existant (get_stock_by_product)

Resultat : success=true, 2 succursales trouvees (Frejus Centre qte=5,
Laval Gare qte=2). Statut : OK

## Test 2 — Stock d'une succursale existante (get_stock_by_branch)

Resultat : success=true, 23 produits avec une quantite strictement
positive retournes pour Frejus Centre. Les trois stocks a zero sont
exclus. Statut : OK

## Test 3 — Succursale inexistante

Resultat : success=false, message "Aucune succursale active trouvee avec
l'identifiant 999999." Statut : OK, pas de crash.

## Test 4 — Produit valide mais sans aucun stock

Resultat : success=true, liste vide (ce n'est pas une erreur). Statut : OK

## Test 5 — check_availability sur plusieurs succursales

Resultat : les deux succursales (Frejus Centre et Laval Gare) apparaissent
dans fully_available_branches, chacune ayant assez de stock pour la
quantite demandee. Statut : OK

## Test 6 — Base de donnees injoignable

Etapes : docker compose stop db, puis relance de manual_test_client.py.

Resultat : les 5 tests retournent tous success=false avec le meme message
clair : "Impossible de se connecter a la base de donnees. Verifiez que le
service de base de donnees est demarre et accessible." Aucun Traceback
Python. Apres docker compose start db, tous les tests repassent a OK.

Statut : OK

## Resume

| Cas teste | Resultat |
|---|---|
| Stock d'un produit existant | OK |
| Stock d'une succursale existante | OK |
| Succursale inexistante | OK |
| Produit sans stock nulle part | OK |
| Disponibilite multi-succursales | OK |
| Base de donnees injoignable | OK |

Ces scénarios sont également couverts automatiquement par `pytest -q`
depuis le dossier `stock_mcp_server`.

## Securite : role mcp_reader

Ce service se connecte uniquement via le role PostgreSQL en lecture seule
mcp_reader (variable MCP_DATABASE_URL), different du compte complet
utilise par le Backoffice (DATABASE_URL). Ce role, configure par
backoffice/init_db.py, ne peut lire que branches et stock, et ne peut
rien ecrire — meme en cas de bug dans notre code, la base de donnees
elle-meme empeche toute fuite vers users ou toute modification du stock
depuis ce service.
