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
- **Activation/désactivation** : `set_active` (refuse l'admin, inexistant),
  routes activate/deactivate (admin only), et login refusé pour un
  compte inactif.

## Résultat d'exécution

La suite a évolué depuis le premier relevé de 84 tests : elle couvre maintenant
également la validation des comptes, la configuration, la seed idempotente, le
bootstrap sur une base partielle et davantage de scénarios E2E.

Pour éviter d'afficher un total ou une couverture périmés, le résultat de la
branche de livraison doit être régénéré avec :

```bash
pytest -q
pytest --cov=. --cov-report=term-missing
pytest e2e/ -q
```

Reporter le commit, la date, le nombre de tests et la couverture obtenue dans
[`../../docs/testing.md`](../../docs/testing.md), section « Preuve à relever sur
le commit final ».

Les fichiers actuellement couverts par la suite incluent :

- règles et services de stock ;
- gestion, normalisation et mots de passe utilisateurs ;
- authentification, sessions et autorisations ;
- contraintes de base de données ;
- intégration de l'API produits ;
- protection CSRF ;
- bootstrap et seed relançable ;
- routes mutatives et validations ;
- parcours E2E du Backoffice.
