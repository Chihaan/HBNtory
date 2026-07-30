# AI Query Service - types de questions supportées

Ce service répond à des questions en langage naturel posées par des
visiteurs **anonymes** via le Client Web. Il s'appuie exclusivement sur des
données réelles obtenues par les serveurs MCP, et n'invente jamais
d'information.

Réponses réellement obtenues pour chacun de ces types :
[`docs/testing.md`](../docs/testing.md).

## Les outils dont dispose l'agent

| Outil | Serveur | Ce qu'il fait |
|---|---|---|
| `list_products(query, limit)` | Product MCP | Cherche des produits par mot-clé |
| `get_product_details(product_id)` | Product MCP | Détails d'un produit, par **id numérique** |
| `list_branches()` | Stock MCP | Les succursales actives et leurs ids |
| `get_stock_by_product(product_id)` | Stock MCP | Où un produit est en stock |
| `get_stock_by_branch(branch_id)` | Stock MCP | Ce que contient une succursale |
| `check_availability(items)` | Stock MCP | Quelle succursale couvre une liste d'achats |

Aucun de ces outils n'écrit. Le stock ne peut être modifié que depuis le
Backoffice authentifié.

## Les 4 types exigés par la consigne

### 1. Détails d'un produit

> Donne-moi les détails du Holberton Student Laptop 14.

Outils : `list_products` puis `get_product_details`.

Deux appels sont nécessaires parce qu'un visiteur donne un **nom**, alors
que `get_product_details` attend un **id numérique**. L'agent résout donc
toujours le nom en id avant de demander les détails.

### 2. Où trouver un produit

> Quelle succursale a le Holberton Student Laptop 14 en stock ?

Outils : `list_products` puis `get_stock_by_product`.

### 3. Ce que contient une succursale

> Quels produits sont disponibles à Fréjus ?

Outils : `list_branches` (pour convertir le nom de la ville en id) puis
`get_stock_by_branch`.

### 4. Liste d'achats sur plusieurs produits

> Je veux 2 Holberton Student Laptop 14 et 1 External SSD 1TB, dans
> quelle succursale aller ?

Outils : un `list_products` par produit, puis `check_availability`.

C'est le type de question le plus intéressant : le raisonnement
« quelle succursale a tout » est fait en SQL par le Stock MCP, pas par le
modèle. L'agent reçoit directement la liste des succursales qui couvrent
la totalité de la commande.

Sur les données de `seed.py`, cette question a une réponse unique :
Fréjus Centre a les deux (5 laptops, 3 SSD), Laval Gare a les laptops mais
0 SSD et est donc écartée.

`fully_available_branches` peut aussi revenir **vide** - par exemple pour
« 2 Holberton Student Laptop 14 et 1 Inventory Tablet 10 », que personne
ne détient ensemble. Ce n'est pas une erreur : `per_branch_breakdown`
donne alors le détail par succursale, et l'agent doit annoncer qu'aucune
ne couvre la commande entière plutôt que d'en désigner une au hasard.

## Hors périmètre

L'agent répond clairement qu'il ne peut pas aider quand la question sort
des produits et du stock. Deux cas distincts :

- **Produit inexistant** - l'agent dit qu'il n'a rien de correspondant,
  sans proposer un produit approchant.
- **Donnée absente des outils** - par exemple le numéro de téléphone d'une
  succursale : l'agent consulte l'outil, constate que le champ n'existe
  pas, et le dit au lieu d'inventer une valeur plausible.

Les demandes de **modification** du stock sont également refusées : aucun
outil ne le permet, et cette opération est réservée au Backoffice.

## Principe anti-hallucination

Chaque affirmation de la réponse finale doit provenir d'un résultat
d'outil. Si un outil retourne `success=false` ou une liste vide, l'agent le
signale au lieu de combler le vide.

Une distinction compte particulièrement : une liste vide n'est **pas** une
erreur. `get_stock_by_product` sur un produit sans stock retourne
`success=true` avec `branches: []`, ce qui doit se traduire par « ce
produit n'est disponible dans aucune succursale » et non par « je n'ai pas
pu vérifier ».

La boucle d'outils est bornée à `MAX_TOOL_ITERATIONS = 6` : une question
mal posée ne peut pas faire tourner l'agent indéfiniment.

## Communication avec le Client Web : REST

`POST /ask`, qui reçoit `{"question": str}` et retourne
`{"answer": str, "tool_calls": list}`.

REST plutôt que WebSocket parce que chaque question est indépendante : il
n'y a aucun historique de conversation à maintenir. Le détail du choix, ses
bénéfices et ses limites : [`docs/architecture.md`](../docs/architecture.md).

Le champ `tool_calls` est la trace des outils MCP réellement appelés. Il
sert au débogage et aux preuves de tests : c'est lui qui permet de vérifier
qu'une réponse s'appuie sur de vraies données.
