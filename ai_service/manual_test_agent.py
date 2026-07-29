import asyncio
import json
import time

from agent import ask_agent

QUESTIONS = [
    ("Details produit", "Donne-moi les details du produit Holberton Student Laptop 14."),
    ("Disponibilite produit", "Ou puis-je trouver le 24 inch Compact Monitor en stock ?"),
    ("Produits d une succursale", "Quels produits sont disponibles a Frejus ?"),
    ("Liste d achats", "Je veux 3 Holberton Student Laptop 14, dans quelle succursale puis-je les trouver ?"),
    ("Hors perimetre", "Quelle est la capitale de la France ?"),
]


async def main() -> None:
    for i, (label, question) in enumerate(QUESTIONS):
        if i > 0:
            print("\nAttente 30s (limite de quota gratuite)...")
            time.sleep(30)
        print("\n" + "=" * 70)
        print("=== " + label + " ===")
        print("Question : " + question)
        result = await ask_agent(question)
        answer = result["answer"]
        calls = result["tool_calls"]
        print("\nReponse : " + str(answer))
        print("\nOutils appeles (" + str(len(calls)) + ") :")
        for call in calls:
            tool_name = call["tool"]
            args = json.dumps(call["arguments"], ensure_ascii=False)
            print("  - " + tool_name + "(" + args + ")")


if __name__ == "__main__":
    asyncio.run(main())