#!/usr/bin/env python3
import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

PRODUCT_API_URL = os.getenv("PRODUCT_API_URL", "http://localhost:5001")
API_PREFIX = os.getenv("PRODUCT_API_PREFIX", "/api/v1")
BASE = f"{PRODUCT_API_URL}{API_PREFIX}"

def list_products():
    try:
        r = requests.get(f"{BASE}/products", params={"include_discontinued": "true", "limit": 100}, timeout=5)
        return {"products": r.json().get("results", [])} if r.status_code == 200 else {"error": str(r.status_code)}
    except Exception as e:
        return {"error": str(e)}

def get_product(product_id: str):
    try:
        r = requests.get(f"{BASE}/products/{product_id}", timeout=5)
        return {"error": "Produit introuvable"} if r.status_code == 404 else r.json()
    except Exception as e:
        return {"error": str(e)}

def list_branches():
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(os.getenv("MCP_DATABASE_URL"))
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name, city FROM branches WHERE is_active = true"))
            return {"branches": [{"id": r.id, "name": r.name, "city": r.city} for r in result]}
    except Exception as e:
        return {"error": str(e)}

def list_stock_by_branch(branch_id: int):
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(os.getenv("MCP_DATABASE_URL"))
        with engine.connect() as conn:
            result = conn.execute(text("SELECT product_id, quantity FROM stock WHERE branch_id = :bid AND quantity > 0"), {"bid": branch_id})
            return {"branch_id": branch_id, "stock": [{"product_id": r.product_id, "quantity": r.quantity} for r in result]}
    except Exception as e:
        return {"error": str(e)}

def find_branches_with_product(product_id: str):
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(os.getenv("MCP_DATABASE_URL"))
        with engine.connect() as conn:
            result = conn.execute(text("SELECT s.branch_id, b.name, b.city, s.quantity FROM stock s JOIN branches b ON s.branch_id = b.id WHERE s.product_id = :pid AND s.quantity > 0 AND b.is_active = true"), {"pid": product_id})
            return {"product_id": product_id, "branches": [{"branch_id": r.branch_id, "name": r.name, "city": r.city, "quantity": r.quantity} for r in result]}
    except Exception as e:
        return {"error": str(e)}

TOOLS_MAP = {
    "list_products": list_products,
    "get_product": get_product,
    "list_branches": list_branches,
    "list_stock_by_branch": list_stock_by_branch,
    "find_branches_with_product": find_branches_with_product,
}

tools = [
    {"type": "function", "function": {"name": "list_products", "description": "Liste tous les produits", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_product", "description": "Details produit", "parameters": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}}},
    {"type": "function", "function": {"name": "list_branches", "description": "Liste succursales", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "list_stock_by_branch", "description": "Stock succursale", "parameters": {"type": "object", "properties": {"branch_id": {"type": "integer"}}, "required": ["branch_id"]}}},
    {"type": "function", "function": {"name": "find_branches_with_product", "description": "Succursales avec produit", "parameters": {"type": "object", "properties": {"product_id": {"type": "string"}}, "required": ["product_id"]}}}
]

SYSTEM_PROMPT = "Tu es un assistant inventaire HBntory. Reponds UNIQUEMENT avec les donnees des tools. Ne jamais inventer. Reponds en francais."

async def ask_agent(question: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]
    while True:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0
        )
        message = response.choices[0].message
        if message.tool_calls:
            messages.append(message)
            for tc in message.tool_calls:
                fn_args = json.loads(tc.function.arguments) or {}
                result = TOOLS_MAP[tc.function.name](**fn_args) if tc.function.name in TOOLS_MAP else {"error": "Tool inconnu"}
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        else:
            return message.content
