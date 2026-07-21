#!/usr/bin/env python3
import requests
from mcp.server.fastmcp import FastMCP

# URL de l'API externe
API_URL = "http://localhost:5001"

mcp = FastMCP("product-server")

@mcp.tool()
def list_products(
    q: str = None,
    category: str = None,
    limit: int = 20,
    offset: int = 0
):
    """Liste tous les produits du catalogue"""
    params = {"limit": limit, "offset": offset}
    if q:
        params["q"] = q
    if category:
        params["category"] = category

    response = requests.get(
        f"{API_URL}/api/v1/products",
        params=params
    )
    return response.json()

@mcp.tool()
def get_product(identifier: str):
    """Obtenir les détails d'un produit par id ou SKU"""
    response = requests.get(
        f"{API_URL}/api/v1/products/{identifier}"
    )
    return response.json()

@mcp.tool()
def search_products(q: str):
    """Chercher un produit par nom, SKU ou tag"""
    response = requests.get(
        f"{API_URL}/api/v1/products/search",
        params={"q": q}
    )
    return response.json()

@mcp.tool()
def list_categories():
    """Liste toutes les catégories de produits"""
    response = requests.get(f"{API_URL}/api/v1/categories")
    return response.json()

@mcp.tool()
def check_health():
    """Vérifie si l'API externe est disponible"""
    response = requests.get(f"{API_URL}/health")
    return response.json()

if __name__ == "__main__":
    mcp.run()