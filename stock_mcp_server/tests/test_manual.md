# Tests manuels - Stock MCP Server

Tests exécutés contre une vraie base PostgreSQL (lancée par `run-dev.sh`),
avec les données de démonstration de `backoffice/seed.py` (succursales
« Fréjus Centre », « Laval Gare », « Toulouse Capitole ») et le rôle en
lecture seule `mcp_reader` créé par `backoffice/init_db.py`.

Vue d'ensemble de tous les tests du projet : [`docs/testing.md`](../../docs/testing.md).

## Prérequis

Le script importe le module serveur et appelle directement les fonctions
d'outil. Il doit être lancé **à l'intérieur du conteneur**, car il résout le
nom de service Docker `db`, qui n'existe pas depuis la machine hôte :

```bash
./run-dev.sh
docker compose exec stock-mcp-server python manual_test_client.py
```

**Attention au `branch_id`.** Le script fixe `KNOWN_BRANCH_ID = 1` en dur,
alors que les identifiants de succursale dépendent de la séquence
PostgreSQL : ils ne valent 1, 2, 3 que sur une base entièrement neuve. Dès
que la base a été recréée, le test 2 échoue alors que le serveur fonctionne
correctement (voir le test 2 ci-dessous).

Avant de lancer le script, relever les identifiants réels :

```bash
docker compose exec stock-mcp-server python -c \
  "import json, server; print(json.dumps(server.list_branches(), indent=2, ensure_ascii=False))"
```

puis ajuster `KNOWN_BRANCH_ID` dans `manual_test_client.py` en conséquence.

Sur la base utilisée pour ces tests, `list_branches()` retourne :

```json
{"success": true, "branches": [
  {"branch_id": 18, "name": "Fréjus Centre",     "city": "Fréjus"},
  {"branch_id": 19, "name": "Laval Gare",        "city": "Laval"},
  {"branch_id": 20, "name": "Toulouse Capitole", "city": "Toulouse"}
], "error": null}
```

## Test 1 - Stock d'un produit existant

**Appel** : `get_stock_by_product(product_id=1)`

**Résultat obtenu** :
```json
{"success": true, "product_id": 1, "branches": [
  {"branch_id": 18, "branch_name": "Fréjus Centre", "city": "Fréjus", "quantity": 10},
  {"branch_id": 19, "branch_name": "Laval Gare",    "city": "Laval",  "quantity": 2}
], "error": null}
```

**Statut** : OK - deux succursales, avec leurs quantités. La jointure sur
`branches` filtre sur `Branch.is_active`, donc une succursale désactivée
n'apparaîtrait pas.

## Test 2 - Stock d'une succursale existante

**Appel tel que le script l'exécute** : `get_stock_by_branch(branch_id=1)`

**Résultat obtenu** :
```json
{"success": false, "branch_id": 1, "branch_name": null, "products": [],
 "error": "Aucune succursale active trouvee avec l'identifiant 1."}
```

Le script affiche donc `ECHEC`. **Ce n'est pas un défaut du serveur** :
aucune succursale ne porte l'identifiant 1 sur cette base, et le serveur
répond exactement ce qu'il doit répondre - une erreur claire, sans crash.
C'est la constante `KNOWN_BRANCH_ID = 1` du script qui est périmée.

**Appel avec un identifiant réel** : `get_stock_by_branch(branch_id=18)`

**Résultat obtenu** : `success=true`, `branch_name="Fréjus Centre"`, et la
liste des lignes de stock sous la forme `{"product_id", "quantity"}`.

**Statut** : OK avec un identifiant valide.

Le nombre de lignes n'est pas indiqué ici volontairement : il dépend de
l'état courant de la base (données de démonstration **plus** toutes les
opérations effectuées depuis le Backoffice). Au moment de l'exécution,
Fréjus Centre comptait 40 lignes, dont 22 avec une quantité strictement
positive.

## Test 3 - Succursale inexistante

**Appel** : `get_stock_by_branch(branch_id=999999)`

**Résultat obtenu** :
```json
{"success": false, "branch_id": 999999, "branch_name": null, "products": [],
 "error": "Aucune succursale active trouvee avec l'identifiant 999999."}
```

**Statut** : OK - erreur claire, aucun `Traceback`.

## Test 4 - Produit valide mais sans aucun stock

**Appel** : `get_stock_by_product(product_id=999999)`

**Résultat obtenu** :
```json
{"success": true, "product_id": 999999, "branches": [], "error": null}
```

**Statut** : OK - et c'est le point important de ce test : `success=true`
avec une liste vide. **Une absence de stock n'est pas une erreur.** La
distinction compte, parce que l'agent doit dire « ce produit n'est
disponible dans aucune succursale » et non « je n'ai pas pu vérifier ».

## Test 5 - `check_availability` sur plusieurs succursales

**Appel** : `check_availability(items=[{"product_id": 1, "quantity": 1}])`

**Résultat obtenu** : Fréjus Centre et Laval Gare apparaissent toutes deux
dans `fully_available_branches`, chacune ayant assez de stock pour la
quantité demandée. `per_branch_breakdown` détaille, par succursale, le
demandé, le disponible et un booléen `sufficient` par produit.

**Statut** : OK

Un cas d'entrée invalide est aussi géré : `items=[]` retourne
`success=false` avec le message « items ne doit pas etre une liste vide. »,
sans ouvrir de session en base.

## Test 6 - Base de données injoignable

**Étapes** : `docker compose stop db`, puis relancer
`manual_test_client.py`.

**Résultat obtenu** : les appels retournent tous `success=false` avec le
même message clair :

```
Impossible de se connecter a la base de donnees. Verifiez que le service
de base de donnees est demarre et accessible.
```

Aucun `Traceback` Python, et aucune information technique divulguée : ni URL
de connexion, ni nom d'utilisateur, ni détail interne de SQLAlchemy. Après
`docker compose start db`, tous les tests repassent à OK.

**Statut** : OK

## Résumé

| Cas testé | Résultat |
|---|---|
| Stock d'un produit existant | OK |
| Stock d'une succursale existante | OK avec un `branch_id` réel - le script en fixe un périmé |
| Succursale inexistante | OK |
| Produit sans stock nulle part | OK |
| Disponibilité multi-succursales | OK |
| Liste d'achats vide | OK |
| Base de données injoignable | OK |

## Sécurité : le rôle `mcp_reader`

Ce service se connecte **uniquement** via le rôle PostgreSQL en lecture
seule `mcp_reader` (variable `MCP_DATABASE_URL`), distinct du compte complet
utilisé par le Backoffice (`DATABASE_URL`).

Ce rôle, configuré par `backoffice/init_db.py`, ne peut lire que `branches`
et `stock`, avec un `REVOKE ALL` explicite sur `users`, et ne peut rien
écrire. Même en cas de bug dans notre code, la base elle-même empêche toute
fuite vers `users` et toute modification du stock depuis ce service.

Deuxième barrière, indépendante : le modèle SQLAlchemy de ce service
(`models.py`) **ne déclare pas la table `users`**. Il n'existe donc aucun
chemin de code capable de la lire, même en écrivant la requête à la main.

## Limites connues

### Le script de test fixe un `branch_id` en dur

`KNOWN_BRANCH_ID = 1` ne vaut que sur une base entièrement neuve. Dès que
la base est recréée, le test 2 signale `ECHEC` alors que le serveur est
correct, ce qui rend la preuve de test trompeuse à la première lecture.

Correction à faire : résoudre la succursale via `list_branches()` au lieu de
la fixer, comme le fait déjà le reste du document. Tant que ce n'est pas
fait, ajuster la constante à la main avant de lancer le script.

### `get_stock_by_branch` ne filtre pas les quantités nulles

`get_stock_by_branch` retourne **toutes** les lignes de stock de la
succursale, y compris celles dont la quantité vaut 0. Une ligne à 0
signifie « ce produit est référencé ici mais épuisé », ce qui n'est pas la
même chose que « disponible ».

Le filtrage est laissé à l'agent, guidé par le prompt système. Un filtre
`quantity > 0` côté outil, ou un champ `in_stock` explicite, serait plus
robuste - c'est l'amélioration à faire en premier sur ce serveur.
