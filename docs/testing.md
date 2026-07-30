# Tests et preuves - HBNtory

Ce document rassemble **toutes** les preuves de tests du projet. Les
chiffres ci-dessous proviennent d'exécutions réelles, pas d'estimations.

## Résumé

| Type de test | Nombre | Commande | Résultat |
|---|---|---|---|
| Tests automatisés Backoffice | **92** | `pytest -q` (dans `backoffice/`) | 92 passés en ~5 s |
| Tests end-to-end (Playwright) | **12** | `pytest e2e/ -q` | 12 passés en ~15 s (Chromium) |
| Tests manuels Product MCP | 3 automatisés + 3 guidés | `python manual_test_client.py` | 3/3 OK |
| Tests manuels Stock MCP | 5 automatisés + 1 guidé | `python manual_test_client.py` | 4/5 OK, 1 artefact du script |
| Scénarios IA de bout en bout | 6 | `curl` sur `POST /ask` | 6/6 réponses correctes |
| Couverture de code (Backoffice) | **87 %** | `pytest --cov=.` | 609 lignes de code applicatif, 80 non couvertes |

## Tests automatisés du Backoffice

### Lancer les tests

```bash
cd backoffice
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Aucune variable d'environnement n'est requise et aucun service externe
n'est nécessaire : `conftest.py` fournit les valeurs par défaut, bascule
sur une base **SQLite en mémoire** quand `DATABASE_URL` n'est pas défini,
et simule les appels à l'API produits. Les tests sont donc reproductibles
sur n'importe quelle machine, sans Docker.

> **Ne jamais lancer la suite avec `DATABASE_URL` pointant sur une base
> utile.** Une fixture `autouse` de `conftest.py` fait `create_all` puis
> `drop_all` à chaque test : la base désignée est vidée de ses tables. Si
> la variable est exportée dans le shell (par exemple pour la stack
> Docker), la neutraliser d'abord : `env -u DATABASE_URL pytest -q`.

Résultat obtenu :

```
92 passed in 4.96s
```

### Répartition par fichier

| Fichier | Tests | Ce qui est vérifié |
|---|---|---|
| `tests/test_services_stock.py` | 21 | Ajout, retrait, listage, validation des quantités, isolation par succursale |
| `tests/test_services_users.py` | 17 | Création, soft delete, activation, changement de mot de passe et de succursale |
| `tests/test_routes_mutations.py` | 10 | Les routes POST modifient réellement la base, redirections, messages flash |
| `tests/test_routes_authz.py` | 10 | Un employé ne peut pas atteindre les pages admin, ni le stock d'une autre succursale |
| `tests/test_routes_auth.py` | 10 | Connexion, déconnexion, mauvais identifiants, comptes supprimés ou désactivés |
| `tests/test_services_products.py` | 7 | Client de l'API produits : succès, 404, panne, timeout |
| `tests/test_db_constraints.py` | 7 | Contraintes SQL : unicité, quantité négative, cohérence rôle/succursale |
| `tests/test_security_csrf.py` | 3 | Un POST sans jeton CSRF est rejeté |
| `tests/test_routes_validation.py` | 3 | Les erreurs de formulaire réaffichent la page sans écrire en base |
| `tests/test_services_auth.py` | 2 | Hachage Argon2 et vérification du mot de passe |
| `tests/test_bootstrap.py` | 2 | Le script de démarrage est idempotent |
| **Total** | **92** | |

### Test sur PostgreSQL réel

Les contraintes `CHECK` et `UNIQUE` se comportent différemment selon le
moteur. La suite est donc aussi exécutée sur PostgreSQL 16 :

```bash
export DATABASE_URL=postgresql+psycopg://hbn:hbn@localhost:5432/hbntest
pytest -q
```

C'est ce que fait le job `test-postgres` de l'intégration continue. Sans
cela, une contrainte pourrait passer les tests SQLite et échouer en
production.

### Couverture

```
pytest -q --cov=. --cov-report=term-missing
```

```
Name                   Stmts   Miss  Cover
------------------------------------------
app.py                    44      0   100%
bootstrap.py              18      3    83%
db.py                     11      1    91%
decorators.py             18      0   100%
forms.py                  18      0   100%
init_db.py                40     26    35%
models.py                 47      3    94%
seed.py                   39     23    41%
services/__init__.py       0      0   100%
services/auth.py          15      0   100%
services/errors.py        10      0   100%
services/products.py      23      0   100%
services/stock.py         47      2    96%
services/users.py         51      0   100%
views/__init__.py          0      0   100%
views/auth.py             43      2    95%
views/stock.py            74      6    92%
views/users.py           111     14    87%
------------------------------------------
TOTAL                    609     80    87%
```

Ce tableau mesure le **code applicatif uniquement**. Les fichiers de
`tests/` en sont exclus par `backoffice/.coveragerc` : ils sont exécutés
par construction, donc couverts à 100 %, et les compter ajouterait 594
lignes toujours vertes qui feraient monter le total à 93 % sans qu'une
seule ligne de plus soit réellement testée. Le chiffre honnête est
**87 %**.

La couche métier (`services/`) est couverte à 100 % sauf `stock.py`
(96 %). C'est volontaire : c'est là que se trouvent les règles à protéger.

Les deux valeurs basses sont assumées :

- `init_db.py` (35 %) et `seed.py` (41 %) sont des scripts d'administration
  exécutés une fois au démarrage. Les tester réellement demanderait de
  créer et détruire une base à chaque exécution ; leur bon fonctionnement
  est vérifié par le démarrage de la stack elle-même.

`views/users.py` (87 %) est le point bas du code réellement servi. Les
14 lignes non couvertes sont exclusivement des branches d'échec : les
`except ServiceError` (rollback + message flash) des routes de
suppression, de changement de mot de passe, de changement de succursale et
d'activation, plus deux branches « formulaire invalide ». Le chemin
nominal de chacune de ces routes est testé ; c'est la remontée d'erreur du
service vers l'affichage qui ne l'est pas.

## Tests end-to-end (Playwright)

Ces tests pilotent un vrai navigateur Chromium pour vérifier ce que les
tests unitaires ne peuvent pas voir : le JavaScript, l'accessibilité au
clavier et l'affichage mobile.

```bash
cd backoffice
pip install -r requirements-e2e.txt
python -m playwright install --with-deps chromium
pytest e2e/ -q
```

12 tests, dans `e2e/test_e2e_smoke.py` :

| Test | Vérifie |
|---|---|
| `test_connexion_aboutit_sur_users` | Le parcours de connexion complet dans un vrai navigateur |
| `test_oeil_affiche_le_mot_de_passe` | Le bouton d'affichage du mot de passe |
| `test_modale_nouvel_employe_s_ouvre` | Ouverture de la modale de création |
| `test_confirmation_mot_de_passe_bloque_si_different` | Validation côté client des deux mots de passe |
| `test_filtres_stock_et_reinitialisation` | Filtres du tableau de stock et remise à zéro |
| `test_carte_en_rupture_filtre_le_tableau` | Clic sur le KPI « en rupture » filtre le tableau |
| `test_un_seul_filtre_deroulant_est_ouvert` | Un seul menu déroulant ouvert à la fois |
| `test_tri_active_la_reinitialisation` | Le tri active le bouton de réinitialisation |
| `test_recherche_stock_par_sku_et_message_accueil` | Recherche par SKU et message d'accueil |
| `test_detail_produit_accessible_au_clavier` | Navigation au clavier sur la fiche produit |
| `test_detail_produit_permet_ajout_et_retrait` | Ajout et retrait depuis la fiche produit |
| `test_stock_reste_utilisable_sur_mobile` | Affichage responsive |

En intégration continue, ce job est marqué `continue-on-error: true` : un
navigateur headless est fragile en CI, et nous ne voulions pas qu'un faux
négatif bloque une fusion. Les jobs bloquants restent la norme PEP8 et les
tests SQLite et PostgreSQL.

## Intégration continue

`.github/workflows/ci.yml`, déclenché à chaque `push` et chaque
`pull_request` :

| Job | Contenu | Bloquant |
|---|---|---|
| `lint` | `pycodestyle --max-line-length=79` | Oui |
| `test-sqlite` | `pytest -q --cov` sur SQLite en mémoire | Oui |
| `test-postgres` | `pytest -q` sur un service PostgreSQL 16 | Oui |
| `test-e2e` | `pytest e2e/ -q` avec Chromium | Non (informatif) |

## Tests manuels des serveurs MCP

Les serveurs MCP sont testés par des scripts qui importent le module
serveur et appellent directement les fonctions d'outil. Ils doivent être
lancés **à l'intérieur du conteneur**, car ils résolvent des noms de
services Docker (`external-products-api`, `db`) qui n'existent pas depuis
la machine hôte :

```bash
docker compose exec mcp-server       python manual_test_client.py
docker compose exec stock-mcp-server python manual_test_client.py
```

### Product MCP Server - 3/3 OK

| Test | Attendu | Obtenu |
|---|---|---|
| 1. Lister les produits | Liste non vide | `count=39` produits, 5 reçus sur la page |
| 2. Produit existant (`id=1`) | Détail complet | `Holberton Student Laptop 14`, SKU `HB-LAP-1001`, 799 USD |
| 3. Produit inexistant | Erreur claire, pas de crash | `Product not found.` |
| 4. API injoignable | Message clair | Guidé : arrêter le conteneur, relancer |
| 5. Panne simulée | HTTP 503 | Guidé : `curl "…/products?force_error=true"` |
| 6. Appel direct des outils | Structure `{success, …, error}` | Guidé : `docker compose exec mcp-server python -c …` |

### Stock MCP Server - 4/5 OK, 1 artefact du script

| Test | Attendu | Obtenu |
|---|---|---|
| 1. `get_stock_by_product(1)` | Succursales et quantités | Fréjus Centre 10, Laval Gare 2 |
| 2. `get_stock_by_branch(1)` | Contenu de la succursale | `ECHEC` - voir ci-dessous |
| 3. Succursale inexistante | Erreur claire | `Aucune succursale active trouvee avec l'identifiant 999999.` |
| 4. Produit sans stock | Liste vide, `success=true` | `branches: []` - une absence de stock n'est pas une erreur |
| 5. `check_availability` | Succursales suffisantes | Fréjus Centre et Laval Gare listées |
| 6. Base injoignable | Message clair | Guidé : `docker compose stop db`, relancer |

> Les quantités du test 1 (Fréjus Centre 10) sont celles de la base **au
> moment de l'exécution**, après des opérations faites depuis le
> Backoffice. Sur une base fraîchement initialisée par `seed.py`, le
> produit 1 est à **5** chez Fréjus Centre et 2 chez Laval Gare. Voir
> l'avertissement de la section suivante.

Le test 2 échoue parce que le script fixe `KNOWN_BRANCH_ID = 1` en dur,
alors que les identifiants de succursale dépendent de la séquence
PostgreSQL - ils valent 18, 19 et 20 sur cette base. **Le serveur est
correct** : il répond `Aucune succursale active trouvee avec l'identifiant 1.`,
soit exactement le comportement attendu pour un identifiant absent. Relancé
avec `branch_id=18`, l'outil retourne bien Fréjus Centre et ses lignes de
stock.

C'est une limite du script de test, pas du serveur, et elle est signalée
dans [`stock_mcp_server/tests/test_manual.md`](../stock_mcp_server/tests/test_manual.md)
avec la correction à apporter.

Le point important du test 4 : un produit qui n'est en stock nulle part
retourne `success=true` avec une liste vide. Ce n'est pas une panne, et
l'agent doit le formuler comme une indisponibilité, pas comme une erreur.

## Preuves de bout en bout de la chaîne IA

Ces six scénarios ont été exécutés sur la stack complète, via
`POST http://localhost:8002/ask`. Ils couvrent les cas demandés par la
consigne. Les traces d'outils sont celles réellement renvoyées par le
service dans le champ `tool_calls`.

> **Sur quelle base ces traces ont été capturées.** La session s'est
> déroulée sur une base **déjà modifiée depuis le Backoffice** : les
> identifiants de succursale valaient 18/19/20 et plusieurs quantités
> avaient été ajustées pendant la mise au point. Les réponses ci-dessous
> sont donc authentiques, mais **elles ne se reproduisent pas à
> l'identique sur une base fraîchement initialisée par `seed.py`**. Les
> écarts sont signalés scénario par scénario. Ce qui doit être vérifié en
> les rejouant, c'est **l'enchaînement des outils** dans `tool_calls`, pas
> les chiffres.

### 1. Où trouver un produit

> **Q :** Quelle succursale a le Holberton Student Laptop 14 en stock ?

> **R :** Fréjus Centre en dispose de 10 unités, Laval Gare de 2 unités.

*Sur une base fraîche : Fréjus Centre 5 unités, Laval Gare 2 unités.*

Outils : `list_products` -> `get_stock_by_product({"product_id": 1})`

L'agent enchaîne correctement : il résout d'abord le nom en identifiant
via le Product MCP, puis interroge le Stock MCP.

### 2. Ce que contient une succursale

> **Q :** Quels produits sont disponibles à Fréjus ?

> **R :** 23 produits, avec leurs quantités.

Outils : `list_branches({})` -> `get_stock_by_branch({"branch_id": 18})` ->
`list_products({"query": "", "limit": 100})` - 3950 ms

*Sur une base fraîche : Fréjus Centre compte 26 lignes de stock, dont 3 à
quantité nulle (produits 4, 11 et 20). `get_stock_by_branch` renvoie les
26 lignes - il ne filtre pas les quantités nulles - et c'est l'agent qui
choisit de ne présenter que ce qui est réellement disponible. Le compte
annoncé dépend donc de cette décision de l'agent, pas de l'outil.*

Trois outils, deux serveurs MCP : la ville devient un `branch_id`, le
stock donne les `product_id` et les quantités, le catalogue fournit les
noms. C'est exactement la combinaison que l'architecture MCP devait
permettre.

### 3. Détail d'un produit

> **Q :** Donne-moi les détails du Holberton Student Laptop 14.

> **R :** Identifiant 1, catégorie Laptops, marque Holberton, prix unitaire
> 799 dollars, poids 1,35 kg, fabriqué par Holberton Tools Co., tags
> student / portable / linux-ready, produit non arrêté.

Outils : `list_products({"query": "Holberton Student Laptop 14"})` - 1830 ms

Toutes les valeurs viennent de l'API produits. Aucune n'est stockée chez
nous.

*Un seul appel a suffi ici : `list_products` renvoie déjà assez de champs
pour cette question, et l'agent n'a pas enchaîné sur
`get_product_details`. Le parcours en deux appels décrit dans
[`QUESTION_TYPES.md`](../ai_service/QUESTION_TYPES.md) reste celui à
attendre quand la question porte sur un champ que seule la route de détail
renvoie - l'objet `supplier`, par exemple. Le choix appartient au modèle.*

### 4. Liste d'achats multi-produits

> **Q :** Je veux 2 Holberton Student Laptop 14 et 1 Inventory Tablet 10,
> dans quelle succursale aller ?

> **R :** Fréjus Centre dispose des deux : 10 unités du laptop et 7 unités
> de la tablette.

Outils : `list_products({"query": "Holberton Student Laptop 14"})` ->
`list_products({"query": "Inventory Tablet 10"})` ->
`check_availability({"items": [{"product_id": 1, "quantity": 2}, {"product_id": 38, "quantity": 1}]})`
en 2522 ms

C'est le scénario qui justifie l'outil `check_availability` : le
raisonnement d'agrégation « quelle succursale a tout » est fait par notre
code SQL, pas par le modèle.

> **Attention, cette réponse n'est pas reproductible.** Le produit 38
> (*Inventory Tablet 10*) n'existe, dans `seed.py`, **qu'à Toulouse
> Capitole** (9 unités) ; Fréjus Centre n'en détient aucune. Du stock
> avait été ajouté à Fréjus depuis le Backoffice avant cette capture. Sur
> une base fraîche, `check_availability` retourne
> `fully_available_branches: []` et l'agent répond, correctement, qu'aucune
> succursale ne couvre la commande entière - en détaillant qui a quoi
> grâce à `per_branch_breakdown`.
>
> **Pour une démonstration sur base fraîche**, utiliser plutôt :
> *« Je veux 2 Holberton Student Laptop 14 et 1 External SSD 1TB, dans
> quelle succursale aller ? »* (produits 1 et 15). Fréjus Centre a les
> deux (5 et 3) et sort seule en `fully_available_branches` ; Laval Gare a
> bien 2 laptops mais 0 SSD et est donc écartée. Cette question démontre
> mieux l'outil, puisqu'elle montre l'agrégation en train de **trancher**
> entre deux succursales.

### 5. Produit absent du catalogue

> **Q :** Avez-vous le produit Nintendo Switch Pro Max en stock ?

> **R :** Nous n'avons aucun produit correspondant à Nintendo Switch Pro Max
> dans notre catalogue.

Outils : `list_products` - 1421 ms

L'agent ne tente pas de deviner un produit approchant, et n'invente pas de
stock. C'est le comportement imposé par le prompt système.

### 6. Question hors périmètre

> **Q :** Quel est le numéro de téléphone de la succursale de Fréjus ?

> **R :** Refus explicite : cette information n'est pas disponible.

Outils : `list_branches({})` - 1458 ms

L'agent consulte l'outil, constate que le numéro de téléphone n'y figure
pas, et le dit - au lieu de produire un numéro plausible.

### Reproduire ces tests

```bash
curl -s -X POST http://localhost:8002/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quelle succursale a le Holberton Student Laptop 14 en stock ?"}'
```

La réponse contient `answer` et `tool_calls`. Le champ `tool_calls` est ce
qui permet de vérifier qu'une réponse s'appuie sur de vraies données et
non sur les connaissances générales du modèle.

## Correspondance consigne -> test

Chaque scénario critique demandé par la consigne, et le test exact qui le
vérifie.

### Scénarios de stock

| Scénario demandé | Test |
|---|---|
| Un employé ajoute du stock valide | `test_services_stock::test_add_stock_cree_une_ligne`, `test_routes_mutations::test_add_stock_ok` |
| Un employé retire du stock valide | `test_services_stock::test_remove_stock_decremente`, `test_routes_mutations::test_remove_stock_ok` |
| Impossible de retirer plus que disponible | `test_services_stock::test_remove_stock_insuffisant` |
| Impossible d'opérer sur une autre succursale | `test_services_stock::test_stock_isole_par_succursale` |
| Les quantités ne peuvent pas devenir négatives | `test_services_stock.py`, `test_db_constraints.py` |
| Un produit n'apparaît qu'une fois par succursale | `test_db_constraints.py` |

### Scénarios de comptes et d'autorisation

| Scénario demandé | Test |
|---|---|
| L'administrateur crée un employé | `test_routes_mutations::test_create_user_ok`, `test_services_users::test_create_user_hache_le_mot_de_passe` |
| L'administrateur supprime un compte (soft delete) | `test_routes_mutations::test_delete_user_ok`, `test_services_users::test_soft_delete_marque_deleted_at` |
| Un compte supprimé ne peut plus se connecter | `test_routes_auth::test_login_utilisateur_supprime_refuse` |
| L'administrateur ne peut pas gérer le stock | `test_routes_authz::test_admin_interdit_sur_stock` |
| Un employé ne peut pas gérer les comptes | `test_routes_authz.py` |
| Un employé ne voit que sa succursale | `test_routes_authz::test_employe_voit_son_stock` |
| L'administrateur n'est rattaché à aucune succursale | `test_db_constraints.py` |
| Les mots de passe ne sont jamais stockés en clair | `test_services_auth.py` |

### Intégration de l'API produits

| Scénario demandé | Test |
|---|---|
| Les détails produit viennent de l'API externe | `test_services_products.py` |
| Une panne de l'API ne casse pas l'affichage | `test_services_products.py` |

### Scénarios IA

Ceux-ci ne sont pas automatisables de façon stable (voir « Ce qui n'est pas
couvert »). Ils sont couverts par les preuves de bout en bout ci-dessus.

| Scénario demandé | Preuve |
|---|---|
| Où un produit est disponible | Scénario 1 |
| Quels produits sont dans une succursale | Scénario 2 |
| Réponse claire pour un produit inconnu | Scénario 5 |
| Réponse claire si l'information est indisponible | Scénario 6 |
| L'IA ne peut pas modifier le stock | Aucun outil MCP d'écriture ; rôle `mcp_reader` en `SELECT` seul |

### Tests au-delà de la consigne

- **CSRF** - jeton absent rejeté, cycle complet du jeton
  (`test_security_csrf`).
- **Contraintes de base** - unicité de `username`, de `(branch_id,
  product_id)` et du nom de succursale ; `CHECK` sur la quantité ;
  cohérence rôle/succursale (`test_db_constraints`).
- **Validation de formulaire** - quantité non entière, champs manquants.
- **Robustesse** - charge utile produit malformée, sans clé attendue, qui
  ne provoque pas de 500.
- **Activation et désactivation** - `set_active` refuse l'administrateur et
  les comptes inexistants ; les routes sont réservées à l'administrateur ;
  la connexion est refusée à un compte inactif.
- **Idempotence du démarrage** - `test_bootstrap.py`.

## Ce qui n'est pas couvert

Par honnêteté, les zones sans test automatisé :

- **Les serveurs MCP n'ont pas de tests `pytest`.** Ils sont validés par
  les scripts manuels ci-dessus. Des tests automatisés demanderaient de
  simuler l'API produits et une base de données ; le choix a été de
  concentrer l'effort automatisé sur le Backoffice, où se trouvent les
  écritures.
- **L'AI Query Service n'a pas de tests automatisés.** Les réponses d'un
  modèle de langage ne sont pas déterministes : un test d'égalité stricte
  serait instable. La validation est faite par les six scénarios
  ci-dessus, avec vérification de la trace d'outils.
- **La limitation de débit n'est pas testée** - elle n'est pas
  implémentée (voir les limites connues dans le README).
- **Le dépassement de quota du fournisseur IA n'est pas géré.** Si Gemini
  répond HTTP 429, l'erreur remonte non capturée et `/ask` retourne 500 ;
  le Client Web affiche seulement « Impossible de contacter le AI Query
  Service. » Reproduit en conditions réelles pendant les tests, avec le
  quota gratuit (15 requêtes par minute).
