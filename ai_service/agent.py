#!/usr/bin/env python3
"""Agent IA de l'AI Query Service, base sur Gemini (Interactions API)."""

import json
import os
from contextlib import AsyncExitStack

from dotenv import load_dotenv
from google import genai

from mcp_client import MCPServerConnection

load_dotenv()

client = genai.Client()

MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
MAX_TOOL_ITERATIONS = 6

PRODUCT_MCP_URL = os.environ["MCP_SERVER_URL"]
STOCK_MCP_URL = os.environ["STOCK_MCP_SERVER_URL"]

SYSTEM_PROMPT = (
    "Tu es l'assistant inventaire de HBntory, une entreprise avec plusieurs "
    "succursales. Reponds UNIQUEMENT a partir des donnees renvoyees par les "
    "outils fournis. Ne jamais inventer un nom de produit, un prix, une "
    "quantite en stock ou une succursale. Si un outil renvoie success=false "
    "ou une liste vide alors qu'un resultat est attendu, dis-le clairement "
    "plutot que de deviner. Pour resoudre le nom d'une succursale (ex: "
    "Frejus) en identifiant, utilise d'abord list_branches. Utilise "
    "toujours l'id numerique du produit (champ id), jamais le sku, pour "
    "appeler les outils. Ne mentionne JAMAIS le champ sku dans tes reponses "
    "a l'utilisateur, c'est un detail technique interne. "
    "Si la question ne concerne pas les produits ou le stock de HBntory, "
    "explique poliment que tu ne peux pas aider. "
    "Reponds en francais, en texte brut uniquement : pas de Markdown, "
    "pas d'asterisques pour le gras, pas de tirets pour les listes. "
    "Pour une liste, ecris simplement une phrase par element, ou separe "
    "les elements par des virgules ou des points-virgules."
)


def _to_gemini_tool(mcp_tool: dict) -> dict:
    return {
        "type": "function",
        "name": mcp_tool["name"],
        "description": mcp_tool["description"],
        "parameters": mcp_tool["input_schema"],
    }


async def ask_agent(question: str) -> dict:
    product_mcp = MCPServerConnection("product-mcp", PRODUCT_MCP_URL)
    stock_mcp = MCPServerConnection("stock-mcp", STOCK_MCP_URL)

    tool_calls_trace: list[dict] = []

    async with AsyncExitStack() as stack:
        await product_mcp.connect(stack)
        await stock_mcp.connect(stack)

        product_tools = await product_mcp.list_tools_anthropic_format()
        stock_tools = await stock_mcp.list_tools_anthropic_format()

        tool_owner = {t["name"]: product_mcp for t in product_tools}
        tool_owner.update({t["name"]: stock_mcp for t in stock_tools})

        gemini_tools = [_to_gemini_tool(t) for t in product_tools + stock_tools]

        history = [
            {"type": "user_input", "content": [{"type": "text", "text": question}]}
        ]

        for _ in range(MAX_TOOL_ITERATIONS):
            interaction = client.interactions.create(
                model=MODEL,
                store=False,
                system_instruction=SYSTEM_PROMPT,
                input=history,
                tools=gemini_tools,
            )

            for step in interaction.steps:
                history.append(step.model_dump())

            function_calls = [s for s in interaction.steps if s.type == "function_call"]

            if not function_calls:
                return {"answer": interaction.output_text, "tool_calls": tool_calls_trace}

            for call in function_calls:
                server = tool_owner.get(call.name)
                if server is None:
                    result_text = json.dumps({"success": False, "error": f"Outil inconnu: {call.name}"})
                else:
                    result_text = await server.call_tool(call.name, call.arguments)

                tool_calls_trace.append({"tool": call.name, "arguments": call.arguments, "result": result_text})
                history.append({
                    "type": "function_result",
                    "name": call.name,
                    "call_id": call.id,
                    "result": [{"type": "text", "text": result_text}],
                })

        return {
            "answer": "Je n'ai pas reussi a obtenir une reponse complete. Merci de reformuler.",
            "tool_calls": tool_calls_trace,
        }
