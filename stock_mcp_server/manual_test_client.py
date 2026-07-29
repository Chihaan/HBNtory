
"""
Script de test manuel rapide pour server.py (Stock MCP Server).

Prerequis:
- La base de donnees tourne (docker compose up -d db).
- MCP_DATABASE_URL est definie (via .env ou export direct).
- Les tables contiennent des donnees de test (via backoffice/bootstrap.py
  ou setup_test_data.py).

Usage:
    python manual_test_client.py
"""

import json

import server

KNOWN_PRODUCT_ID = 1     # doit correspondre a un product_id present dans stock
KNOWN_BRANCH_ID = 1      # doit correspondre a un branch_id existant

print("=== Test 1: Stock d'un produit existant (get_stock_by_product) ===")
result = server.get_stock_by_product(product_id=KNOWN_PRODUCT_ID)
print(json.dumps(result, indent=2, ensure_ascii=False))
print("OK" if result["success"] else "ECHEC")

print("\n=== Test 2: Stock d'une succursale existante (get_stock_by_branch) ===")
result = server.get_stock_by_branch(branch_id=KNOWN_BRANCH_ID)
print(json.dumps(result, indent=2, ensure_ascii=False))
print("OK" if result["success"] else "ECHEC")

print("\n=== Test 3: Succursale inexistante ===")
result = server.get_stock_by_branch(branch_id=999999)
print(json.dumps(result, indent=2, ensure_ascii=False))
if not result["success"] and "999999" in result["error"]:
    print("OK - erreur claire retournee, pas de crash.")
else:
    print("ECHEC - comportement inattendu.")

print("\n=== Test 4: Produit sans aucun stock nulle part ===")
result = server.get_stock_by_product(product_id=999999)
print(json.dumps(result, indent=2, ensure_ascii=False))
if result["success"] and result["branches"] == []:
    print("OK - liste vide retournee, ce n'est pas une erreur (produit valide, juste pas en stock).")
else:
    print("ECHEC - comportement inattendu.")

print("\n=== Test 5: check_availability sur plusieurs produits ===")
result = server.check_availability(items=[
    {"product_id": KNOWN_PRODUCT_ID, "quantity": 1},
])
print(json.dumps(result, indent=2, ensure_ascii=False))
print("OK" if result["success"] else "ECHEC")

print("\n=== Test 6: Base de donnees injoignable ===")
print("Pour tester ce cas: arretez le service de base de donnees")
print("(docker compose stop db), puis relancez ce script. Vous devez voir")
print("un message d'erreur clair, pas un crash Python (Traceback).")
