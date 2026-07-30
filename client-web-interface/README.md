# Client Web - HBNtory

Interface publique où un visiteur **anonyme** pose une question en langage
naturel sur les produits et le stock. Aucune authentification.

- Adresse : <http://localhost:8080>
- Servie par nginx (`nginx:alpine`), en pages statiques
- Interroge l'AI Query Service sur `POST http://localhost:8002/ask`

## Fichiers

| Fichier | Rôle |
|---|---|
| `index.html` | La page : un champ de question, un indicateur d'attente, une zone de réponse |
| `script.js` | Envoie la question, affiche `answer` |
| `style.css` | Mise en forme |
| `nginx.conf` | **Non utilisé** - voir la note ci-dessous |

> `nginx.conf` n'est pas chargé. Le service `client-web` du
> `docker-compose.yml` utilise l'image `nginx:alpine` telle quelle et monte
> ce dossier comme racine statique ; la configuration par défaut de nginx
> s'applique donc. Le fichier est un reste d'une approche par proxy inverse
> qui n'a pas été retenue : `script.js` appelle directement l'AI Query
> Service. Son bloc `location /api/` désigne d'ailleurs
> `http://ai_service:8000`, qui ne correspond ni au nom du service
> (`ai-service`) ni à son port (`8002`).

## Stratégie de communication : REST

Le client parle à l'AI Query Service en REST, pas en WebSocket.

**Pourquoi REST** - Chaque question est indépendante : il n'y a aucun
historique de conversation à maintenir. Cela donne une implémentation
simple, un débogage facile (`curl` suffit à reproduire n'importe quel cas)
et un contrat requête/réponse clair.

**Ce qu'on y perd** - Pas de streaming : l'utilisateur attend la réponse
complète, soit 1,4 à 4 secondes en pratique. Pas de communication
bidirectionnelle.

**Pourquoi pas WebSocket** - Ce serait justifié pour du streaming token par
token ou une session de chat avec mémoire. Ni l'un ni l'autre n'est requis
ici, et une connexion persistante ajouterait de l'état à gérer pour un gain
purement cosmétique.

## Le contrat d'API

Requête :

```json
POST /ask
{"question": "Quelle succursale a le Holberton Student Laptop 14 en stock ?"}
```

Réponse :

```json
{
  "answer": "Fréjus Centre en dispose de 5 unités, Laval Gare de 2 unités.",
  "tool_calls": [
    {"name": "list_products",        "args": {"query": "Holberton Student Laptop 14"}},
    {"name": "get_stock_by_product", "args": {"product_id": 1}}
  ]
}
```

La page n'affiche que `answer`. Le champ `tool_calls` sert au débogage et
aux preuves de tests : c'est lui qui permet de vérifier qu'une réponse
s'appuie sur de vraies données et non sur les connaissances générales du
modèle.

Test en ligne de commande :

```bash
curl -s -X POST http://localhost:8002/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quelles succursales avez-vous ?"}'
```

## Questions d'exemple

**Où trouver un produit**

> Quelle succursale a le Holberton Student Laptop 14 en stock ?

**Ce que contient une succursale**

> Quels produits sont disponibles à Fréjus ?

**Détails d'un produit**

> Donne-moi les détails du Holberton Student Laptop 14.

**Liste d'achats sur plusieurs produits**

> Je veux 2 Holberton Student Laptop 14 et 1 External SSD 1TB, dans
> quelle succursale aller ?

C'est la question la plus intéressante à poser en démonstration : l'agent
résout deux noms de produits, puis appelle `check_availability` pour
déterminer quelle succursale peut tout fournir. Sur les données de
`seed.py`, la réponse est Fréjus Centre seule - Laval Gare a les laptops
mais 0 SSD.

Variante à connaître : remplacer l'*External SSD 1TB* par l'*Inventory
Tablet 10* (produit 38, présent uniquement à Toulouse) donne un
`fully_available_branches` **vide**. L'agent doit alors dire qu'aucune
succursale ne couvre la commande entière, pas en désigner une.

**Produit qui n'existe pas** - l'agent répond qu'il n'a rien de
correspondant, sans proposer un produit approchant :

> Avez-vous le produit Nintendo Switch Pro Max en stock ?

**Information hors périmètre** - l'agent constate que la donnée n'est pas
dans ses outils et le dit, au lieu d'inventer :

> Quel est le numéro de téléphone de la succursale de Fréjus ?

Réponses réellement obtenues pour ces six questions :
[`docs/testing.md`](../docs/testing.md).

## CORS

L'AI Query Service autorise toutes les origines (`allow_origins=["*"]`),
parce que le client est servi sur le port 8080 et appelle une API sur le
port 8002 : ce sont deux origines différentes pour le navigateur.

Acceptable ici, puisque l'API est déjà publique et en lecture seule. Pour
une mise en production, il faudrait restreindre la liste aux origines
réellement attendues.

## Limites connues

- **Le code de statut HTTP n'est pas vérifié.** `script.js` ne teste pas
  `res.ok` et lit directement `data.answer`. Si le service renvoyait une
  erreur au format JSON - par exemple une erreur de validation 422,
  `{"detail": [...]}` - la page afficherait « undefined ». Ce cas n'est pas
  atteignable depuis l'interface, qui envoie toujours un champ `question`
  non vide.
- **Un HTTP 500 s'affiche comme une erreur réseau.** FastAPI renvoie alors
  `Internal Server Error` en texte brut ; `res.json()` échoue et le bloc
  `catch` affiche « Impossible de contacter le AI Query Service. » Le
  message est trompeur : le service a bien répondu. C'est ce qui se produit
  quand le quota Gemini est dépassé.
- **Pas de limitation de débit.** N'importe qui peut envoyer des questions
  en boucle et consommer le quota de l'API Gemini.
- **Pas d'historique.** Chaque question est indépendante ; « et à Laval ? »
  ne fonctionnera pas comme question de suivi.
- **Réponse en texte brut.** `textContent` est utilisé plutôt que
  `innerHTML` - un choix délibéré, qui empêche toute injection HTML depuis
  une réponse du modèle, au prix d'une mise en forme absente.
