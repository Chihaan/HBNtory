# Preuve de tests — Backoffice HBNtory

Ce document relie chaque scénario critique demandé par la consigne aux
tests automatisés qui le vérifient, et donne les commandes pour les
rejouer. Périmètre : le **Backoffice** (authentification, gestion du
stock par succursale, gestion des utilisateurs, intégration API
produits). Les scénarios liés à l'**IA** relèvent du service AI Query
(hors de ce module).

## Comment rejouer les tests

Depuis `backoffice/` :

```bash
pip install -r requirements-dev.txt

# Suite unitaire + intégration (SQLite en mémoire)
pytest -q

# Avec couverture détaillée
pytest --cov=. --cov-report=term-missing

# Sur PostgreSQL réel (fidèle à la prod)
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/db \
SECRET_KEY=x PRODUCTS_API_URL=http://localhost:5001 pytest -q

# Tests end-to-end (navigateur, JS réel)
pip install -r requirements-e2e.txt
python -m playwright install --with-deps chromium
pytest e2e/ -q
```

## Couverture des scénarios critiques (consigne — Task 2)

| Scénario demandé | Test | Statut |
|---|---|---|
| Common user ajoute du stock valide | `test_services_stock::test_add_stock_cree_une_ligne`, `test_routes_mutations::test_add_stock_ok` | ✅ |
| Common user retire du stock valide | `test_services_stock::test_remove_stock_decremente`, `test_routes_mutations::test_remove_stock_ok` | ✅ |
| Ne peut pas retirer plus que disponible | `test_services_stock::test_remove_stock_insuffisant` | ✅ |
| Ne peut pas opérer sur une autre succursale | `test_services_stock::test_stock_isole_par_succursale` | ✅ |
| Admin crée un common user | `test_routes_mutations::test_create_user_ok`, `test_services_users::test_create_user_hache_le_mot_de_passe` | ✅ |
| Admin soft-delete un utilisateur | `test_routes_mutations::test_delete_user_ok`, `test_services_users::test_soft_delete_marque_deleted_at` | ✅ |
| Un utilisateur supprimé ne peut plus se connecter | `test_routes_auth::test_login_utilisateur_supprime_refuse` | ✅ |
| Admin ne peut pas gérer le stock | `test_routes_authz::test_admin_interdit_sur_stock` | ✅ |
| Détails produit via l'API externe | `test_services_products::*`, `test_routes_authz::test_employe_voit_son_stock` | ✅ |
| IA : où un produit est disponible | Service AI Query (hors Backoffice) | ⤴ autre module |
| IA : produits disponibles dans une branche | Service AI Query (hors Backoffice) | ⤴ autre module |
| IA : réponse claire pour produit inconnu | Service AI Query (hors Backoffice) | ⤴ autre module |
| IA : réponse claire si info indisponible | Service AI Query (hors Backoffice) | ⤴ autre module |

## Tests supplémentaires (au-delà de la consigne)

- **Sécurité** : protection CSRF active et cycle complet du jeton
  (`test_security_csrf`), redirections d'autorisation 403 et
  `login_required`, dégradation gracieuse si l'API produits tombe.
- **Contraintes base** : unicité (`username`, `branch+product`, nom de
  succursale), `CHECK` quantité ≥ 0, cohérence rôle/succursale — la base
  rejette elle-même les données incohérentes (`test_db_constraints`).
- **Validation formulaire** : quantité non entière, champs manquants.
- **Robustesse API** : payload produit malformé sans clé (pas de 500).

## Résultat d'exécution

Suite complète : **76 tests, 100 % au vert** (SQLite en mémoire).

| Fichier | Tests |
|---|---|
| test_services_stock.py | 18 |
| test_services_users.py | 13 |
| test_services_products.py | 7 |
| test_services_auth.py | 2 |
| test_routes_auth.py | 9 |
| test_routes_authz.py | 8 |
| test_routes_mutations.py | 8 |
| test_routes_validation.py | 2 |
| test_db_constraints.py | 6 |
| test_security_csrf.py | 3 |
| **Total** | **76** |

Plus **4 tests end-to-end** (Playwright, dans `e2e/`) : connexion
complète, bascule d'affichage du mot de passe, ouverture de modale,
blocage de la confirmation de mot de passe divergente.

## Couverture (`pytest --cov`)

```
app.py              100%   decorators.py       100%   forms.py            100%
services/auth.py    100%   services/products   100%   services/stock.py   100%
services/users.py   100%   views/auth.py       100%
views/stock.py       85%   views/users.py       88%   models.py            93%
TOTAL                91%
```

Logique métier (`services/*`) couverte à **100 %**. Le non-couvert
restant : scripts d'exploitation (`seed.py`, `init_db.py`), les
`__repr__`, la branche moteur Postgres de `db.py`, et les pages de repli
GET héritées.
