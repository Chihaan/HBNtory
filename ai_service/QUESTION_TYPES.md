# AI Query Service - Types de questions supportees

## Objectif

Ce service repond a des questions en langage naturel posees par des
utilisateurs anonymes via le Client Web, en s'appuyant exclusivement sur
des donnees reelles obtenues via le Product MCP Server et le Stock MCP
Server. Il n'invente jamais d'information.

## Types de questions supportees (minimum requis)

1. Details d'un produit
   Exemple : "Donne-moi les details du produit HB-LAP-1001"
   Outils utilises : list_products, get_product_details.

2. Disponibilite d'un produit
   Exemple : "Ou puis-je trouver le produit X ?"
   Outils utilises : list_products / get_product_details, get_stock_by_product.

3. Produits disponibles dans une succursale
   Exemple : "Quels produits sont disponibles a Frejus ?"
   Outils utilises : list_branches (resoudre le nom en id), get_stock_by_branch.

4. Liste d'achats sur plusieurs produits
   Exemple : "Je veux 3 laptops et 2 ecrans, dans quelle(s) succursale(s) ?"
   Outils utilises : list_products / get_product_details, check_availability.

## Hors perimetre

Le service repond clairement qu'il ne peut pas aider si la question ne
concerne pas les produits ou le stock (ex: questions generales, demandes
de modification de stock - reservees au Backoffice authentifie).

## Principe anti-hallucination

L'agent doit toujours passer par les outils MCP pour obtenir des
informations. Si un outil retourne success=false ou une liste vide,
l'agent le signale clairement plutot que d'inventer une valeur.

## Communication avec le Client Web : REST

Choix REST plutot que WebSocket : chaque question est traitee
independamment (pas d'historique de conversation a maintenir). WebSocket
ne se justifierait que pour du streaming ou une vraie session de chat
avec memoire, ce qui n'est pas requis ici.

Endpoint : POST /ask, recoit {"question": str}, retourne
{"answer": str, "tool_calls": list} (la trace des outils MCP appeles,
utile pour observer/debugger le raisonnement de l'agent).