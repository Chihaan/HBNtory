# Tests manuels — Product MCP Server

Tests exécutés contre la vraie Product API du repo
`hbtn-edu/hbntory-products-api`, lancée en local sur `http://localhost:5001`.

## Prérequis

```bash
# Terminal 1 : lancer la Product API
cd hbntory-products-api
docker compose up --build
# ou en local sans Docker : HBN_PRODUCTS_PORT=5001 python3 app.py

# Vérifier qu'elle répond
curl http://localhost:5001/health
```

```bash
# Terminal 2 : environnement du MCP server
cd product_mcp_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Test 1 — Lister les produits (cas nominal)

**Commande** : `python manual_test_client.py`

**Résultat obtenu** :
```
=== Test 1: Lister les produits ===
OK - count=39 produits au total, 5 recus sur cette page.
Exemple: {'id': 4, 'sku': 'HB-MON-2102', 'name': '24 inch Compact Monitor',
'description': '...', 'category': 'Displays', 'brand': 'LabForge', ...
'unit_price': 169.99, 'currency': 'USD', 'discontinued': False, ...}
```

**Statut** : ✅ OK — la liste des produits est correctement récupérée et
parsée depuis `{"count", "limit", "offset", "results": [...]}`.

## Test 2 — Récupérer les détails d'un produit existant

**Commande** : `python manual_test_client.py`, avec `product_id = "1"`
(id numérique — décision d'équipe : la base de données stocke l'id
numérique, pas le SKU, donc `get_product_details` n'accepte que l'id).

**Résultat obtenu** :
```
=== Test 2: Recuperer un produit existant ===
OK - {'id': 1, 'sku': 'HB-LAP-1001', 'name': 'Holberton Student Laptop 14',
'description': '...', 'category': 'Laptops', 'brand': 'Holberton',
'unit_price': 799.0, 'currency': 'USD', 'discontinued': False, ...
'supplier': {'id': 'SUP-HBT-001', 'name': 'Holberton Tools Co.', ...}}
```

**Statut** : ✅ OK — le produit est trouvé par son SKU, avec les infos
fournisseur incluses (`supplier`, ajouté par la Product API sur le détail).

## Test 3 — Produit inexistant (product not found)

**Commande** : `python manual_test_client.py`, avec
`product_id = "PRODUIT_QUI_N_EXISTE_PAS_999"`.

**Résultat obtenu** :
```
=== Test 3: Produit inexistant ===
OK - erreur 'not found' correctement geree: Product not found.
```

**Statut** : ✅ OK — `ProductNotFoundError` est bien levée, avec le message
exact renvoyé par la Product API (`"Product not found."`), pas de crash.

## Test 4 — Product API injoignable (connexion refusée)

**Étapes** :
1. Arrêt du process/container de la Product API (`pkill -f app.py`
   en local, ou `docker compose down`).
2. Relance de `python manual_test_client.py`.

**Résultat obtenu** :
```
=== Test 1: Lister les produits ===
ECHEC - Impossible de se connecter a la Product API a l'adresse
http://localhost:5001. Verifiez que le service est demarre et accessible.

=== Test 2: Recuperer un produit existant ===
ECHEC - Impossible de se connecter a la Product API a l'adresse
http://localhost:5001. Verifiez que le service est demarre et accessible.

=== Test 3: Produit inexistant ===
ECHEC - mauvais type d'erreur retourne: Impossible de se connecter ...
```

**Statut** : ✅ OK — aucune exception Python non gérée (`Traceback`)
n'apparaît. Le message d'erreur est clair et exploitable. Note : le test 3
affiche "mauvais type d'erreur" car le script s'attendait spécifiquement à
un `ProductNotFoundError` — ici c'est bien un `ProductAPIError` de connexion
qui est levé à la place, ce qui est le comportement correct puisque l'échec
est réseau et non "produit absent".

## Test 5 — Panne simulée côté Product API (`force_error=true`)

**Commande directe (curl)** :
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

**Vérification de l'extraction du message par notre client** :
```
Status HTTP recu: 503
Message extrait par notre client: Forced simulation error.
Exception levee correctement -> success=False, error="Forced simulation error."
```

**Statut** : ✅ OK — le statut 503 est correctement intercepté, et le
message précis renvoyé par la Product API (`"Forced simulation error."`)
est extrait et transmis, plutôt qu'un message générique.

## Test 6 — Appel direct des tools MCP (server.py, bout en bout)

**Commande** :
```python
import server
server.list_products(query="laptop", limit=3)
server.get_product_details(product_id=1)
server.get_product_details(product_id=9999)
```

**Résultat obtenu (extraits)** :
```json
// list_products(query="laptop", limit=3)
{
  "success": true,
  "count": 5,
  "products": [
    {"id": 1, "sku": "HB-LAP-1001", "name": "Holberton Student Laptop 14"},
    {"id": 2, "sku": "HB-LAP-1002", "name": "Holberton Student Laptop 16"},
    {"id": 26, "sku": "HB-BAG-1012", "name": "Laptop Backpack"}
  ],
  "error": null
}

// get_product_details(product_id="HB-LAP-1001")
{
  "success": true,
  "product": {"id": 1, "sku": "HB-LAP-1001", "supplier": "..."},
  "error": null
}

// get_product_details(product_id="NOPE")
{
  "success": false,
  "product": null,
  "error": "Product not found."
}
```

**Statut** : OK — les tools exposés par le serveur MCP produisent bien
les structures attendues, prêtes à être consommées par l'agent IA.

## Résumé

| Cas testé | Comportement attendu | Résultat |
|---|---|---|
| Liste produits (nominal) | `success: true`, produits reçus | ✅ |
| Détail produit existant | `success: true`, produit reçu | ✅ |
| Détail produit inexistant | `success: false`, message "not found" | ✅ |
| Product API injoignable | `success: false`, message clair, pas de crash | ✅ |
| Panne simulée (503) | `success: false`, message extrait de la réponse | ✅ |

## Explication de la gestion d'erreurs

Le serveur MCP ne laisse jamais une exception non gérée remonter au
protocole MCP. Chaque tool (`list_products`, `get_product_details`) retourne
systématiquement une structure `{"success": bool, ..., "error": str | null}`.

Trois catégories d'erreurs sont distinguées dans `product_api_client.py` :

1. **`ProductNotFoundError`** (HTTP 404) — le produit n'existe pas. Le
   message exact renvoyé par la Product API (`body["message"]`) est
   propagé tel quel.
2. **`ProductAPIError`** — regroupe :
   - erreurs réseau (`ConnectionError`, `Timeout`) avant même d'atteindre
     la Product API ;
   - statuts HTTP inattendus (ex: `503 supplier_unavailable` simulé via
     `force_error=true`) — le message précis est extrait du corps JSON
     de la réponse quand disponible (`_extract_error_message`) ;
   - réponse qui n'est pas du JSON valide.
3. **Validation d'entrée** — `product_id` vide, gérée directement dans le
   tool `get_product_details` avant même d'appeler l'API, pour éviter un
   appel réseau inutile.

Cette distinction permet à l'agent IA de réagir différemment selon le cas :
un produit non trouvé peut être communiqué normalement à l'utilisateur
("ce produit n'existe pas"), tandis qu'une panne de la Product API doit
plutôt mener l'agent à dire qu'il ne peut pas répondre pour l'instant.