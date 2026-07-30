# Preuve de tests - Backoffice

Les preuves de tests de tout le projet sont centralisées dans
**[`docs/testing.md`](../../docs/testing.md)** : chiffres d'exécution,
répartition par fichier, couverture, tests end-to-end, tests manuels des
serveurs MCP, preuves de bout en bout de la chaîne IA, et correspondance
entre chaque scénario de la consigne et le test qui le vérifie.

Ce fichier ne duplique volontairement plus ces chiffres : deux documents
qui comptent les mêmes tests finissent toujours par se contredire.

## Rejouer les tests du Backoffice

Depuis `backoffice/` :

```bash
pip install -r requirements-dev.txt

export SECRET_KEY=test-secret
export PRODUCTS_API_URL=http://products.test

# Suite complète (SQLite en mémoire, aucun service externe requis)
pytest -q

# Avec le détail de couverture
pytest --cov=. --cov-report=term-missing

# Sur PostgreSQL réel
DATABASE_URL=postgresql+psycopg://hbntory:changeme@localhost:5432/hbntory pytest -q

# Tests end-to-end (navigateur)
pip install -r requirements-e2e.txt
python -m playwright install --with-deps chromium
pytest e2e/ -q
```

## Périmètre

Ce module couvre l'authentification, l'autorisation, la gestion du stock
par succursale, la gestion des comptes et l'intégration de l'API produits.

Les scénarios liés à l'IA relèvent de l'AI Query Service et des serveurs
MCP ; leurs preuves sont dans [`docs/testing.md`](../../docs/testing.md) et
dans les fichiers `tests/test_manual.md` de chaque serveur MCP.
