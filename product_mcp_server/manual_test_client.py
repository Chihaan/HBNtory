"""
Script de test manuel rapide pour product_api_client.py.
A executer AVANT de tester via l'inspecteur MCP, pour verifier que la
communication avec la Product API fonctionne independamment du protocole MCP.

Prerequis: la Product API (repo hbntory-products-api) doit tourner via
`docker compose up --build`, disponible sur http://localhost:5001.

Usage:
    python manual_test_client.py
"""

from product_api_client import (
    fetch_products,
    fetch_product_by_id,
    ProductAPIError,
    ProductNotFoundError,
)

KNOWN_PRODUCT_ID = "1"  # id numerique reel present dans data/products.json (Holberton Student Laptop 14)

print("=== Test 1: Lister les produits ===")
try:
    payload = fetch_products(limit=5)
    results = payload.get("results", [])
    print(f"OK - count={payload.get('count')} produits au total, {len(results)} recus sur cette page.")
    if results:
        print(f"Exemple: {results[0]}")
except ProductAPIError as e:
    print(f"ECHEC - {e.message}")

print("\n=== Test 2: Recuperer un produit existant ===")
try:
    product = fetch_product_by_id(KNOWN_PRODUCT_ID)
    print(f"OK - {product}")
except ProductNotFoundError as e:
    print(f"ECHEC - produit connu non trouve: {e.message}")
except ProductAPIError as e:
    print(f"ECHEC - {e.message}")

print("\n=== Test 3: Produit inexistant ===")
try:
    product = fetch_product_by_id("PRODUIT_QUI_N_EXISTE_PAS_999")
    print(f"ECHEC - un produit a ete retourne alors qu'il ne devrait pas exister: {product}")
except ProductNotFoundError as e:
    print(f"OK - erreur 'not found' correctement geree: {e.message}")
except ProductAPIError as e:
    print(f"ECHEC - mauvais type d'erreur retourne: {e.message}")

print("\n=== Test 4: Product API injoignable (connexion refusee) ===")
print("Pour tester ce cas : arretez le container de la Product API (docker compose down),")
print("puis relancez ce script. Vous devez voir un message d'erreur clair, pas un crash Python.")

print("\n=== Test 5 (bonus): Panne simulee via force_error=true ===")
print("La Product API expose ce cas nativement via le parametre ?force_error=true.")
print("Ce script Python n'appelle pas ce parametre directement (product_api_client ne")
print("l'expose pas), mais vous pouvez le verifier manuellement avec curl:")
print('  curl "http://localhost:5001/api/v1/products?force_error=true"')
print("Attendu: HTTP 503 avec {\"error\": \"supplier_unavailable\", ...}")
