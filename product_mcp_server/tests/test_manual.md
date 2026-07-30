# Tests manuels - Product MCP Server

Tests exécutés contre la vraie Product API fournie par Holberton, présente
dans ce dépôt sous `external/product-api/` (dossier non modifié).

Vue d'ensemble de tous les tests du projet : [`docs/testing.md`](../../docs/testing.md).

## Prérequis

Le script `manual_test_client.py` importe **`product_api_client`**, pas
`server` : il vérifie la couche qui parle à la Product API,
indépendamment du protocole MCP. C'est délibéré - si cette couche est
saine, une erreur d'outil MCP ne peut venir que de l'enveloppe
`{success, …, error}`, laquelle est vérifiée séparément par le **test 6**,
qui lui importe bien le module `server` et appelle les outils.

Les tests 1 à 3 appellent donc `fetch_products()` et
`fetch_product_by_id()`, dont les retours sont les dictionnaires **bruts**
de l'API - pas encore l'enveloppe MCP.

Le script doit être lancé **à l'intérieur du conteneur**, car il résout le
nom de service Docker `external-products-api`, qui n'existe pas depuis la
machine hôte.

```bash
# Depuis la racine du dépôt
./run-dev.sh

# Vérifier que la Product API répond (depuis l'hôte)
curl http://localhost:5001/health

# Lancer les tests
docker compose exec mcp-server python manual_test_client.py
```

| Adresse | Depuis l'hôte | Depuis un conteneur |
|---|---|---|
| Product API | `http://localhost:5001` | `http://external-products-api:5000` |

Les messages d'erreur ci-dessous citent l'adresse vue **depuis le
conteneur**, c'est-à-dire la valeur de `PRODUCT_API_URL`.

## Note sur les identifiants

L'endpoint `/api/v1/products/{id}` de la Product API accepte techniquement
l'id numérique **et** le SKU. Notre système n'utilise volontairement que
l'**id numérique**, car c'est cet identifiant qui est stocké dans la table
`stock` pour associer une quantité à un produit.

C'est appliqué par la signature de l'outil : `get_product_details(product_id: int)`.
Un SKU ne peut donc pas être passé via MCP. La description de l'outil
`list_products` le précise aussi explicitement à l'agent : il faut passer
le champ `id`, pas le champ `sku`.

## Test 1 - Lister les produits (cas nominal)

**Commande** : `docker compose exec mcp-server python manual_test_client.py`

**Résultat obtenu** :
```
=== Test 1: Lister les produits ===
OK - count=39 produits au total, 5 recus sur cette page.
Exemple: {'id': 4, 'sku': 'HB-MON-2102', 'name': '24 inch Compact Monitor',
'category': 'Displays', 'brand': 'LabForge', 'unit_price': 169.99,
'currency': 'USD', 'discontinued': False, ...}
```

**Statut** : OK - la liste est correctement récupérée et lue depuis la
structure de pagination `{"count", "limit", "offset", "results": [...]}`.

## Test 2 - Détails d'un produit existant

**Appel** : `fetch_product_by_id("1")` - la couche client, pas encore
l'outil MCP (voir les prérequis). Le retour est donc le dictionnaire brut
de l'API, sans l'enveloppe `{success, product, error}`.

**Résultat obtenu** :
```
=== Test 2: Recuperer un produit existant ===
OK - {'id': 1, 'sku': 'HB-LAP-1001', 'name': 'Holberton Student Laptop 14',
'category': 'Laptops', 'brand': 'Holberton', 'unit_price': 799.0,
'currency': 'USD', 'discontinued': False, 'weight_kg': 1.35,
'tags': ['student', 'portable', 'linux-ready'],
'supplier': {'id': 'SUP-HBT-001', 'name': 'Holberton Tools Co.',
'lead_time_days': 5, 'reliability_score': 0.97}}
```

**Statut** : OK - le produit est trouvé **par son id numérique**. Le
détail contient un objet `supplier` que la liste ne renvoie pas : la
Product API l'ajoute uniquement sur la route d'un produit seul.

## Test 3 - Produit inexistant

**Appel** : `fetch_product_by_id("PRODUIT_QUI_N_EXISTE_PAS_999")` - c'est
l'identifiant que le script utilise réellement. Il n'est même pas
numérique, ce qui vérifie au passage que la Product API répond 404 sur
n'importe quel identifiant inconnu, id ou SKU.

**Résultat obtenu** :
```
=== Test 3: Produit inexistant ===
OK - erreur 'not found' correctement geree: Product not found.
```

**Statut** : OK - `ProductNotFoundError` est levée, avec le message
renvoyé par la Product API et non un message générique de notre cru. C'est
`server.get_product_details()` qui la convertit ensuite en
`{"success": false, "product": null, "error": "Product not found."}` -
conversion vérifiée par le **test 6**.

## Test 4 - Product API injoignable

**Étapes** :
1. `docker compose stop external-products-api`
2. `docker compose exec mcp-server python manual_test_client.py`

**Résultat obtenu** :
```
=== Test 1: Lister les produits ===
ECHEC - Impossible de se connecter a la Product API a l'adresse
http://external-products-api:5000. Verifiez que le service est demarre et accessible.

=== Test 2: Recuperer un produit existant ===
ECHEC - Impossible de se connecter a la Product API a l'adresse
http://external-products-api:5000. Verifiez que le service est demarre et accessible.

=== Test 3: Produit inexistant ===
ECHEC - mauvais type d'erreur retourne: Impossible de se connecter ...
```

**Statut** : OK - aucun `Traceback` Python. Le message est clair et nomme
l'adresse effectivement utilisée.

Le test 3 affiche « mauvais type d'erreur » et c'est **le comportement
correct** : le script attendait un `ProductNotFoundError`, mais l'échec est
réseau, donc un `ProductAPIError` de connexion est levé à la place. Une
panne réseau ne doit pas être présentée comme « produit absent » - la
distinction compte, car l'agent doit réagir différemment dans les deux cas.

Ne pas oublier de relancer le service : `docker compose start external-products-api`.

## Test 5 - Panne simulée (`force_error=true`)

La Product API sait simuler une panne fournisseur. Vérification directe :

```bash
curl -s -w "\nHTTP_STATUS:%{http_code}\n" \
  "http://localhost:5001/api/v1/products?force_error=true"
```

**Résultat obtenu** :
```
{
  "error": "supplier_unavailable",
  "message": "Forced simulation error."
}
HTTP_STATUS:503
```

**Extraction du message par notre client** :
```
Status HTTP recu: 503
Message extrait par notre client: Forced simulation error.
```

**Statut** : OK - le statut 503 est intercepté et `_extract_error_message`
récupère le message précis du corps JSON, plutôt que de retomber sur
« statut inattendu: 503 ».

Le script `manual_test_client.py` n'appelle pas ce paramètre lui-même
(`product_api_client` ne l'expose pas) : ce cas se vérifie par le `curl`
ci-dessus.

## Test 6 - Appel direct des outils MCP

**Commande** :
```bash
docker compose exec mcp-server python -c "
import json, server
print(json.dumps(server.list_products(query='laptop', limit=3), indent=2))
print(json.dumps(server.get_product_details(product_id=1), indent=2))
print(json.dumps(server.get_product_details(product_id=9999), indent=2))
"
```

**Résultat obtenu (extraits)** :
```json
// list_products(query="laptop", limit=3)
{
  "success": true,
  "count": 5,
  "products": [
    {"id": 1,  "sku": "HB-LAP-1001", "name": "Holberton Student Laptop 14"},
    {"id": 2,  "sku": "HB-LAP-1002", "name": "Holberton Student Laptop 16"},
    {"id": 26, "sku": "HB-BAG-1012", "name": "Laptop Backpack"}
  ],
  "error": null
}

// get_product_details(product_id=1)
{
  "success": true,
  "product": {"id": 1, "sku": "HB-LAP-1001",
              "name": "Holberton Student Laptop 14",
              "supplier": {"name": "Holberton Tools Co.", "...": "..."}},
  "error": null
}

// get_product_details(product_id=9999)
{
  "success": false,
  "product": null,
  "error": "Product not found."
}
```

**Statut** : OK - `count: 5` alors que 3 produits sont retournés : `count`
est le **total correspondant côté fournisseur**, `products` est la page
demandée. C'est voulu, et la description de l'outil le dit à l'agent.

## Résumé

| Cas testé | Comportement attendu | Résultat |
|---|---|---|
| Liste produits (nominal) | `success: true`, produits reçus | OK |
| Détail produit existant | `success: true`, produit et fournisseur | OK |
| Détail produit inexistant | `success: false`, `"Product not found."` | OK |
| Product API injoignable | `success: false`, message clair, pas de crash | OK |
| Panne simulée (503) | `success: false`, message extrait de la réponse | OK |

## Gestion des erreurs

Le serveur MCP ne laisse **jamais** une exception non gérée remonter au
protocole MCP. Chaque outil retourne systématiquement une structure
`{"success": bool, ..., "error": str | null}`.

Deux catégories d'erreurs sont distinguées dans `product_api_client.py` :

1. **`ProductNotFoundError`** (HTTP 404) - le produit n'existe pas. Le
   message renvoyé par la Product API (`body["message"]`) est propagé tel
   quel.
2. **`ProductAPIError`** - tout le reste :
   - erreurs réseau (`ConnectionError`, `Timeout`) avant même d'atteindre
     la Product API ;
   - statuts HTTP inattendus (ex. `503 supplier_unavailable` via
     `force_error=true`), avec extraction du message précis du corps JSON
     quand il est disponible ;
   - réponse qui n'est pas du JSON valide.

`ProductNotFoundError` hérite de `ProductAPIError`, donc l'ordre des blocs
`except` compte : le cas « non trouvé » est intercepté en premier.

Cette distinction permet à l'agent IA de réagir différemment : un produit
non trouvé peut être communiqué normalement à l'utilisateur (« ce produit
n'existe pas dans notre catalogue »), tandis qu'une panne de la Product API
doit l'amener à dire qu'il ne peut pas répondre pour le moment.

Le timeout est fixé à 5 secondes, volontairement au-dessus des 3000 ms que
la Product API accepte via `?simulate_delay_ms` : une réponse lente mais
volontaire ne doit pas être coupée, tout en gardant une borne finie pour ne
jamais bloquer le serveur MCP.

## Limite connue

Il n'y a **pas de validation de `product_id` avant l'appel réseau**. Un
identifiant absurde mais numérique (`product_id=-1`) déclenche un appel à
la Product API, qui répond 404. Le comportement est correct pour
l'utilisateur, mais un appel réseau inutile est effectué. La signature
`int` de l'outil élimine déjà le cas le plus probable - une chaîne vide ou
un SKU.
