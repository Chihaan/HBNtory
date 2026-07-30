# Plan de présentation - HBNtory

Durée imposée : **10 minutes** de présentation et démonstration, puis
**5 minutes** de questions. Chaque membre de l'équipe doit intervenir.

La consigne insiste sur la clarté et la compréhension du système, pas sur
le soin visuel. Ce plan privilégie donc la démonstration en direct sur les
diapositives.

## Avant de commencer - checklist

À faire **avant** de présenter, pas devant le jury :

```bash
./run-dev.sh
docker compose ps                    # les 7 services doivent être "running"
```

```bash
# La chaîne IA répond (la première question est toujours la plus lente)
curl -s -X POST http://localhost:8002/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quelles succursales avez-vous ?"}'
```

| Point | Pourquoi |
|---|---|
| Onglets déjà ouverts sur `:8000` et `:8080` | Ne pas taper d'URL en direct |
| Déconnecté du Backoffice | La démo commence par l'authentification |
| Quota Gemini non épuisé | 15 requêtes/minute en offre gratuite - ne pas répéter la démo IA juste avant |
| Mots de passe de démo à portée de main | `admin` / `marie` |
| Diagrammes ouverts en local | `docs/architecture.md` et `docs/database.md` s'affichent avec les diagrammes rendus sur GitHub |
| Noms de produits repris **à l'identique** du catalogue | La recherche est une simple sous-chaîne, sur un catalogue en anglais : « laptop 14 » trouve le produit, « laptop 14 pouces » ne trouve **rien** |

> Le point du quota est le vrai risque de la démo : si Gemini répond 429,
> `/ask` retourne 500 et le client affiche seulement un message d'échec de
> contact. Espacer les questions.

## Déroulé minute par minute

### 1. Ce que fait le système - 1 min

Une entreprise de vente au détail avec plusieurs succursales doit suivre
son stock. Deux publics, deux applications :

- les **employés** gèrent le stock de leur succursale, l'**administrateur**
  gère les comptes ;
- les **clients** posent des questions en langage naturel, sans compte.

Point à faire passer : les données produit ne sont pas à nous. Elles
viennent d'une API externe fournie. Nous ne stockons que le stock, les
succursales et les comptes.

### 2. L'architecture - 2 min

Montrer le diagramme de [`architecture.md`](architecture.md) et suivre les
**deux chemins** :

- **Écriture** - Employé -> Backoffice -> PostgreSQL. Authentifié, c'est le
  seul chemin par lequel le stock peut changer.
- **Lecture IA** - Visiteur -> Client Web -> AI Service -> serveurs MCP ->
  base et API. Anonyme, et en lecture seule de bout en bout.

La phrase à dire : *« un visiteur anonyme ne peut pas modifier le stock,
parce qu'aucun outil MCP n'expose d'écriture et parce que le Stock MCP se
connecte à PostgreSQL avec un rôle qui n'a que le privilège SELECT. »*

C'est le point d'architecture le plus solide du projet : la sécurité vient
de la forme du système, pas d'une vérification qu'on pourrait oublier.

Si le jury demande **comment** l'agent utilise concrètement les outils, le
diagramme de séquence du même fichier (section « Comment l'agent utilise les
outils MCP ») déroule une vraie question, appel par appel. À garder sous la
main plutôt qu'à présenter : c'est une réponse, pas une slide.

### 3. Démonstration - 4 min 30

C'est le cœur de la note. Les cinq étapes exigées par la consigne, dans
cet ordre :

**a. Authentification du Backoffice** (30 s)

Se connecter en `marie`. Montrer au passage que l'en-tête affiche sa
succursale : Fréjus Centre.

**b. Gestion du stock par un employé** (1 min 30)

- Le tableau de stock ne montre **que** Fréjus Centre - pas les autres
  succursales.
- Ajouter des unités sur un produit : la quantité change.
- Retirer plus d'unités qu'il n'y en a : message d'erreur métier clair,
  et **la base n'est pas modifiée**.
- Dire la règle sans la démontrer : la succursale n'est jamais un
  paramètre, elle est déduite de l'utilisateur connecté. Il n'y a pas de
  champ à falsifier.

**c. Gestion des comptes par l'administrateur** (1 min)

Se reconnecter en `admin`.

- Créer un employé rattaché à une succursale.
- Montrer que l'administrateur, lui, n'est rattaché à aucune succursale -
  et que c'est une contrainte de la base, pas une convention.
- Supprimer un compte : c'est un *soft delete*, la ligne reste, mais la
  connexion est refusée immédiatement.

**d. Requête produit via le Client Web** (45 s)

Sur `:8080`, poser :

> Quelle succursale a le Holberton Student Laptop 14 en stock ?

Réponse attendue : Fréjus Centre 5 unités, Laval Gare 2 unités.

> Ces quantités sont celles de `seed.py` sur une base fraîche. Si du stock
> a été ajouté ou retiré pendant les répétitions - ou pendant l'étape **b**
> juste avant - les chiffres auront bougé. Relever les vraies valeurs avant
> de présenter, ou annoncer la réponse sans citer de nombre.

**e. Réponse IA combinant produit et stock** (45 s)

> Je veux 2 Holberton Student Laptop 14 et 1 External SSD 1TB, dans
> quelle succursale aller ?

Réponse attendue : **Fréjus Centre uniquement**. Elle a les deux (5 laptops
et 3 SSD). Laval Gare a bien 2 laptops, mais 0 SSD : elle est écartée.

C'est **la** question à poser, parce qu'elle prouve la valeur de
l'architecture : l'agent résout deux noms de produits via le Product MCP,
puis appelle `check_availability` sur le Stock MCP. Deux serveurs MCP, deux
sources de données, une seule réponse. Et le fait que Laval Gare soit
écartée montre que l'agrégation **tranche** réellement, au lieu de
recopier une liste.

> **Ne pas poser la question avec l'*Inventory Tablet 10*** (produit 38).
> Elle n'existe qu'à Toulouse Capitole, et Fréjus Centre n'en a aucune :
> la réponse serait « aucune succursale ne peut tout fournir ». Une trace
> de test de `docs/testing.md` montre le contraire, mais elle avait été
> capturée sur une base modifiée à la main - c'est signalé sur place.

Si le temps le permet, montrer aussi le refus honnête :

> Quel est le numéro de téléphone de la succursale de Fréjus ?

L'agent consulte l'outil, constate que le numéro n'y figure pas, et le
dit - au lieu d'inventer un numéro plausible.

### 4. Décisions techniques et compromis - 1 min 30

Trois décisions à défendre, une phrase chacune :

| Décision | Justification en une phrase |
|---|---|
| Argon2id plutôt que SHA-256 | SHA-256 est conçu pour être rapide, donc facile à attaquer par force brute ; Argon2 est conçu pour être lent et coûteux en mémoire. |
| Sessions plutôt que JWT | Une session est révocable immédiatement : un compte supprimé perd l'accès au prochain clic, alors qu'un JWT reste valide jusqu'à son expiration. |
| Serveur MCP sur mesure plutôt qu'un MCP base de données générique | Un outil `query(sql)` laisserait le modèle écrire du SQL arbitraire ; quatre outils métier typés rendent une lecture de la table `users` impossible à exprimer. |

Compromis assumés, à dire franchement :

- pas de limitation de débit sur `/ask` ;
- une erreur de quota du fournisseur IA remonte en HTTP 500 non gérée ;
- la validation des `product_id` est prospective : elle bloque les
  nouveaux identifiants invalides, elle ne détecte pas ceux déjà présents.

Avec plus de temps : historique des mouvements de stock, journal d'audit,
gestion propre des erreurs du fournisseur IA.

### 5. Tests - 30 s

Chiffres réels, sans arrondi flatteur :

- 92 tests automatisés, 87 % de couverture du code applicatif (les
  fichiers de tests sont exclus de la mesure : les compter la ferait
  monter à 93 % sans rien tester de plus) ;
- suite exécutée sur SQLite **et** sur PostgreSQL réel, parce que les
  contraintes `CHECK` ne se comportent pas de la même façon ;
- 12 tests end-to-end sous Chromium ;
- intégration continue à chaque push.

Détail dans [`testing.md`](testing.md).

## Répartition entre les membres

Proposition à ajuster selon qui a écrit quoi - l'important est que chacun
présente une partie qu'il maîtrise, puisque le jury pose des questions
techniques.

| Partie | Membre |
|---|---|
| Présentation du projet et architecture | Vadim Gavet |
| Démonstration du Backoffice (stock et comptes) | Madi Anli Madi |
| Démonstration du Client Web et de la chaîne IA | Adib |
| Décisions techniques et tests | tous, sur sa propre partie |

## Questions probables et réponses

Anticiper ces questions évite d'improviser :

**« Pourquoi ne pas stocker les noms de produits dans votre base ? »**
Parce qu'il faudrait les resynchroniser. Un prix modifié côté fournisseur
serait immédiatement faux chez nous. Le coût de ce choix, c'est qu'on perd
la clé étrangère - remplacée par une vérification applicative.

**« Que se passe-t-il si l'API produits tombe ? »**
Le stock reste consultable, avec les quantités mais sans les noms. Seul le
référencement d'un produit entièrement nouveau est bloqué, car c'est le
seul cas qui a besoin de valider un identifiant.

**« L'IA pourrait-elle lire la table des mots de passe ? »**
Non, et pour deux raisons indépendantes. Aucun outil MCP n'expose la table
`users` - le modèle SQLAlchemy du Stock MCP ne la déclare même pas. Et le
rôle PostgreSQL `mcp_reader` n'a `SELECT` que sur `branches` et `stock`,
avec un `REVOKE ALL` explicite sur `users`.

**« Comment empêchez-vous un employé de modifier une autre succursale ? »**
Les fonctions de service ne prennent pas `branch_id` en paramètre : elles
le déduisent de l'utilisateur connecté. La fraude n'est pas rendue
difficile, elle est impossible à exprimer.

**« Pourquoi l'agent fait-il plusieurs appels d'outils ? »**
Parce que produits et stock sont dans deux sources différentes. Un nom de
produit doit d'abord devenir un identifiant, avant que le stock puisse
être interrogé. La trace de ces appels est renvoyée dans `tool_calls`, ce
qui permet de vérifier qu'une réponse s'appuie sur de vraies données.

**« Que feriez-vous différemment ? »**
Gérer les erreurs du fournisseur IA proprement, et ajouter un historique
des mouvements de stock - c'est ce qui manque le plus à un outil
d'inventaire réel.

## Diagrammes disponibles

| Diagramme | Où |
|---|---|
| Vue d'ensemble (résumé) | [`../README.md`](../README.md) |
| Architecture des services | [`architecture.md`](architecture.md) |
| Chaîne IA -> MCP (séquence) | [`architecture.md`](architecture.md) |
| Schéma de la base (ERD) | [`database.md`](database.md) |
| Séquence de connexion | [`security.md`](security.md) |
| Défense en profondeur | [`security.md`](security.md) |

Ils sont écrits en Mermaid et se rendent directement sur GitHub : pas
besoin d'outil externe pour les montrer.
