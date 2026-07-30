# Tests et validation d'intégration

## Objectif

Ce document relie les scénarios critiques des consignes aux vérifications du
projet. Il distingue :

- les tests automatisés présents dans le dépôt ;
- les contrôles manuels nécessaires avec la vraie stack ;
- la preuve finale à relever après exécution sur la branche de livraison.

Une suite présente dans le dépôt n'est pas considérée comme exécutée tant que
sa commande n'a pas été relancée sur le commit final.

## Préparer les environnements de tests

Chaque service possède ses dépendances de développement :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Installer ensuite les dépendances du composant à tester, par exemple :

```bash
python -m pip install -r backoffice/requirements-dev.txt
```

Il est aussi possible d'utiliser quatre environnements virtuels séparés pour
éviter les conflits de dépendances.

## Suites automatisées

Depuis la racine du dépôt :

```bash
(cd backoffice && pytest -q)
(cd product_mcp_server && pytest -q)
(cd stock_mcp_server && pytest -q)
(cd ai_service && pytest -q)
```

Contrôles complémentaires :

```bash
(cd backoffice && pytest --cov=. --cov-report=term-missing)
(cd backoffice && pytest e2e/ -q)
node --check client-web-interface/script.js
docker compose config --quiet
bash -n run-dev.sh smoke-test.sh backoffice/docker-entrypoint.sh
```

Les tests E2E Backoffice nécessitent Playwright :

```bash
python -m pip install -r backoffice/requirements-e2e.txt
python -m playwright install chromium
(cd backoffice && pytest e2e/ -q)
```

## Matrice des scénarios obligatoires

| Scénario | Couverture présente |
| --- | --- |
| un common user ajoute du stock valide | `backoffice/tests/test_services_stock.py`, `test_routes_mutations.py` |
| un common user retire du stock valide | `backoffice/tests/test_services_stock.py`, `test_routes_mutations.py` |
| retrait supérieur au stock refusé | `backoffice/tests/test_services_stock.py` |
| opération sur une autre succursale impossible | `backoffice/tests/test_services_stock.py`, `test_routes_authz.py` |
| l'admin crée un common user | `backoffice/tests/test_services_users.py`, `test_routes_mutations.py` |
| l'admin soft-delete un utilisateur | `backoffice/tests/test_services_users.py`, `test_routes_mutations.py` |
| un utilisateur supprimé ne se connecte plus | `backoffice/tests/test_routes_auth.py` |
| l'admin ne gère pas le stock | `backoffice/tests/test_routes_authz.py` |
| les produits viennent de l'API externe | `backoffice/tests/test_services_products.py`, tests du Product MCP |
| les outils Product MCP gèrent liste, détail, 404 et panne | `product_mcp_server/tests/test_server.py` |
| le Stock MCP répond par produit et par succursale | `stock_mcp_server/tests/test_server.py` |
| le Stock MCP calcule une liste multi-produits | `stock_mcp_server/tests/test_server.py` |
| l'agent exécute des outils MCP avant de répondre | `ai_service/tests/test_agent.py` |
| l'endpoint refuse une question vide ou trop longue | `ai_service/tests/test_app.py` |
| les erreurs IA publiques sont contrôlées | `ai_service/tests/test_app.py`, `test_timeouts.py` |
| le client envoie le bon contrat à l'AI Service | `ai_service/tests/test_flux_client_web.py` |
| les appels d'outils sont observables sans fuite | `ai_service/tests/test_observabilite.py` |

Les tests unitaires de l'agent emploient des doubles de test. Ils vérifient la
boucle d'orchestration, mais ne remplacent pas les questions réalistes avec le
modèle et les données réelles.

## Validation manuelle du flux complet

### 1. Démarrage

```bash
./run-dev.sh
```

Dans un autre terminal :

```bash
docker compose ps
curl -fsS http://localhost:5001/health
curl -fsS http://localhost:8002/health
curl -fsS http://localhost:8080/ >/dev/null
```

Tous les services doivent être `healthy`.

### 2. Backoffice

À partir de <http://localhost:8000> :

1. se connecter comme utilisateur commun ;
2. vérifier que le nom de sa succursale est visible ;
3. ajouter une quantité positive ;
4. retirer une quantité disponible ;
5. tenter de retirer davantage que le stock ;
6. confirmer qu'aucune autre succursale n'est sélectionnable ;
7. se connecter comme `admin` ;
8. créer un utilisateur commun avec une succursale ;
9. changer son mot de passe et sa succursale ;
10. le soft-delete, puis vérifier que sa connexion est refusée ;
11. vérifier que l'admin reçoit `403` sur les routes de stock.

### 3. Product MCP

Suivre `product_mcp_server/tests/test_manual.md` et vérifier :

- liste nominale ;
- détail d'un produit existant ;
- produit inconnu ;
- API produits arrêtée.

### 4. Stock MCP

Suivre `stock_mcp_server/tests/test_manual.md` et vérifier :

- stock d'un produit entre plusieurs succursales ;
- produits d'une succursale ;
- succursale inconnue ;
- liste d'achats sur une ou plusieurs succursales ;
- base arrêtée.

### 5. Client Web et agent réel

Ouvrir <http://localhost:8080> et noter la réponse obtenue pour :

1. « Donne-moi les détails du produit 12. »
2. « Dans quelles succursales puis-je trouver le produit 3 ? »
3. « Quels produits sont disponibles à Fréjus ? »
4. « Je veux 3 unités du produit 1, 2 unités du produit 3 et 4 unités du
   produit 7. Où dois-je aller ? »
5. « Donne-moi les détails du produit 999999. »
6. une question hors sujet, par exemple « Écris-moi un poème. »

Résultats attendus :

- les quatre premières réponses correspondent aux données réelles ;
- le produit inconnu n'est pas inventé ;
- la question hors sujet est refusée clairement ;
- les journaux `ai-service` montrent les outils appelés ;
- le navigateur affiche une erreur claire si un service est arrêté.

Pour le scénario de démonstration multi-produits, la seed annonce la réponse
attendue au démarrage. Avec les données initiales, Fréjus Centre peut fournir
seule les quantités demandées.

### 6. Dégradations contrôlées

Arrêter temporairement un service, faire le contrôle, puis le redémarrer :

```bash
docker compose stop external-products-api
docker compose start external-products-api

docker compose stop stock-mcp-server
docker compose start stock-mcp-server

docker compose stop ai-service
docker compose start ai-service
```

Vérifier qu'aucun message ne contient de mot de passe, de clé API ou de chaîne
de connexion.

## Smoke test

```bash
./smoke-test.sh
```

Ce mode vérifie le trajet Client Web → Nginx → AI Service sans appeler le
modèle. Pour une requête réelle :

```bash
./smoke-test.sh --avec-ia
```

Le smoke test réel confirme que l'endpoint renvoie une réponse, mais les six
questions de la section précédente restent nécessaires pour valider la qualité
fonctionnelle et le grounding.

## Preuve à relever sur le commit final

Compléter ce tableau après la dernière exécution :

| Vérification | Commit | Date | Résultat |
| --- | --- | --- | --- |
| Backoffice pytest | à renseigner | à renseigner | à renseigner |
| Product MCP pytest | à renseigner | à renseigner | à renseigner |
| Stock MCP pytest | à renseigner | à renseigner | à renseigner |
| AI Service pytest | à renseigner | à renseigner | à renseigner |
| Backoffice E2E | à renseigner | à renseigner | à renseigner |
| Compose + smoke sans IA | à renseigner | à renseigner | à renseigner |
| six questions réelles | à renseigner | à renseigner | à renseigner |

Conserver avec la livraison :

- la sortie des commandes ;
- une capture du `docker compose ps` ;
- les réponses des six questions ;
- si possible, une courte capture vidéo de la démonstration.
