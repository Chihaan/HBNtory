# Règles de validation du stock

Ce document explique **où** la validation du stock est appliquée dans le
Backoffice, et **pourquoi** chaque règle se trouve à cet endroit.

## Où vit la validation

Le Backoffice est organisé en trois couches :

| Couche | Fichiers | Rôle |
|---|---|---|
| Vue | `views/` | Parle HTTP : lit le formulaire, convertit `"5"` en `5`, sait qui est connecté via `current_user` |
| Service | `services/` | Parle métier : décide si une opération est autorisée, puis l'applique |
| Modèle | `models.py` | Décrit ce qu'est une ligne de stock et ses contraintes |

**Toute la validation du stock vit dans la couche service.**

Elle n'est pas dans la vue, car il faudrait la répéter dans chaque route,
et tout appelant qui n'est pas une vue - un script, un test, un futur
serveur MCP - la contournerait. Une règle qu'on peut ignorer en changeant
d'appelant n'est pas une règle.

Elle n'est pas non plus dans le modèle. Un validateur de modèle ne peut
pas faire l'appel réseau nécessaire pour vérifier un produit auprès de
l'API externe, et il ne sait rien de l'utilisateur qui agit. Le modèle
décrit une ligne, pas une opération.

La couche service est le seul endroit qui voit à la fois **qui agit** et
**ce qui est écrit**. C'est le passage le plus étroit par lequel toute
écriture doit transiter, donc c'est là que la validation a lieu, avant que
quoi que ce soit n'atteigne la base.

## Contraintes de base de données ou vérifications applicatives

Deux couches protègent les données, et elles ne protègent pas la même
chose.

La base garantit l'**état final**. Une contrainte
`CHECK (quantity >= 0)` assure qu'aucune quantité stockée n'est jamais
négative, quel que soit le code qui écrit dans la table. C'est la dernière
ligne de défense, et elle ne peut pas être contournée.

Le service garantit le **sens de l'opération**. Une contrainte `CHECK` ne
voit que la valeur résultante, pas l'intention. Prenons un retrait avec une
quantité négative :

```
stock actuel = 4
remove_stock(quantity=-5)
4 - (-5) = 9
```

Le résultat, 9, est positif. La contrainte est satisfaite et PostgreSQL
accepte - alors que l'employé vient de transformer un retrait en un ajout
déguisé. La base n'a jamais vu de violation, car il n'y en a pas eu. Seule
une vérification applicative (« la quantité doit être un entier
strictement positif ») attrape ce cas, parce que seul le service sait que
l'opération était censée être un retrait.

**La contrainte protège la valeur stockée ; le service protège
l'intention.**

## Les règles appliquées

| Règle | Où | Pourquoi |
|---|---|---|
| Quantité entière strictement positive | `_validate_quantity` (service) | Distingue un retrait d'un ajout déguisé |
| Le retrait ne peut pas dépasser le stock disponible | `remove_stock` (service) | Message métier clair plutôt qu'une erreur SQL |
| Quantité stockée jamais négative | `CHECK` en base | Filet de sécurité, quel que soit l'appelant |
| Quantité plafonnée à 1 000 000 | `_validate_addition_limit` + `CHECK` | Empêche une faute de frappe de créer un stock absurde |
| Un produit une seule fois par succursale | `UNIQUE (branch_id, product_id)` | Évite deux lignes contradictoires pour le même produit |
| Le `product_id` doit exister dans l'API | `product_exists()` (service) | Remplace la clé étrangère impossible à créer |

## Pourquoi la succursale n'est pas un paramètre

Les services ne prennent **jamais** `branch_id` en argument. Il est
toujours lu depuis l'utilisateur authentifié :

```python
branch_id = _user_branch_id(user)
```

Si `branch_id` était un paramètre, l'appelant déciderait quelle succursale
modifier, et la sécurité dépendrait du fait que chaque route pense à
vérifier que l'utilisateur a le droit de désigner cette succursale. Une
seule vérification oubliée, et un employé pourrait modifier le stock d'une
autre succursale en changeant un champ caché du formulaire.

En dérivant la succursale de l'utilisateur, la fraude n'est pas rendue
difficile : elle devient **impossible à exprimer**. Il n'y a aucun
paramètre à falsifier. L'autorisation n'est plus une vérification qu'on
peut oublier, c'est une propriété de la signature de la fonction.

`_user_branch_id` lève aussi `NoBranchAssigned` quand l'utilisateur n'a
pas de succursale (l'administrateur, dont `branch_id` vaut `NULL`). Elle
**retourne** la valeur au lieu de se contenter de la vérifier, pour que le
contrôle ne puisse pas être sauté : sans elle, il n'y a pas de `branch_id`
avec lequel continuer.

## Vérification de l'identifiant produit

Les lignes de stock ne stockent qu'un `product_id`, **sans clé
étrangère**, parce que les données produit vivent dans une API externe et
jamais dans notre base. Rien dans le schéma n'empêche donc d'écrire un
identifiant invalide. La vérification dans la couche service est le
substitut applicatif de la clé étrangère qu'on ne peut pas créer.

L'API est interrogée via `product_exists()`, sur la route
`/api/v1/products/{id}` - la route d'un **produit seul**, pas la liste. La
liste exclut par défaut les produits arrêtés, ce qui signalerait à tort le
produit 32 comme inconnu alors que nous en détenons du stock. « Arrêté »
n'est pas « inexistant ».

La vérification n'a lieu **que lorsqu'une nouvelle ligne de stock est
créée** - c'est-à-dire quand `add_stock` ne trouve aucune ligne existante
pour `(branch_id, product_id)`. C'est le seul moment où un identifiant non
validé pourrait entrer en base. Ajouter à une ligne existante, ou en
retirer, n'appelle jamais l'API.

Cela rend la dépendance externe peu coûteuse et sûre. Si l'API est en
panne, `product_exists` lève `ProductApiUnavailable`, et seul le
référencement d'un produit **entièrement nouveau** est bloqué. Consulter
le stock, ajouter à un produit existant ou retirer du stock continuent de
fonctionner.

## Limite connue

La validation des produits est **prospective** : elle empêche de nouveaux
identifiants invalides d'entrer, mais ne détecte pas ceux déjà présents.
Les lignes insérées en dehors de la couche service - en particulier les
données de démonstration - ne sont pas couvertes.

Si le projet devait durer, un petit script d'audit listant les
`product_id` orphelins serait la réponse. Dans un projet de deux semaines,
c'est un compromis assumé, pas un oubli.

## Documents liés

- [`database.md`](database.md) - les contraintes SQL exactes
- [`security.md`](security.md) - autorisation et isolation par succursale
- [`testing.md`](testing.md) - les tests qui vérifient ces règles
