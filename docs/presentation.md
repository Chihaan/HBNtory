# Présentation finale HBNtory

## Format

- Présentation et démonstration : 10 minutes.
- Questions : 5 minutes.
- Chaque membre de l'équipe intervient.

Cette trame peut être transformée en diapositives. Elle privilégie une
démonstration fiable et des explications techniques courtes.

## Déroulé proposé

### 1. Problème et solution — 45 secondes

HBNtory gère le stock de plusieurs succursales sans dupliquer le catalogue
produits externe. Les employés utilisent un Backoffice sécurisé ; le public
pose des questions en langage naturel.

À montrer :

- une capture du Backoffice ;
- une capture du Client Web.

### 2. Architecture — 1 minute 15

Afficher le diagramme de `docs/architecture.md`.

Messages importants :

- sept services avec des responsabilités séparées ;
- PostgreSQL ne conserve que les utilisateurs, succursales, identifiants
  produit et quantités ;
- le Backoffice est le seul service qui écrit du stock ;
- l'agent accède aux données uniquement par MCP.

### 3. Base et règles métier — 1 minute

Afficher l'ERD de `docs/database-schema.md`.

Expliquer :

- un common user appartient exactement à une succursale ;
- l'admin n'a pas de succursale ;
- une ligne de stock est unique par succursale et produit ;
- les contraintes interdisent les quantités négatives ;
- les détails produits ne sont pas stockés localement.

### 4. Authentification et autorisation — 1 minute

Expliquer :

- sessions Flask-Login ;
- mots de passe Argon2 ;
- refus des comptes désactivés ou soft-deleted ;
- décorateurs de rôle côté backend ;
- succursale dérivée de l'utilisateur, jamais d'un paramètre client ;
- formulaires protégés par CSRF.

### 5. MCP et agent IA — 1 minute 15

Expliquer :

- Product MCP : liste et détails depuis l'API externe ;
- Stock MCP : requêtes en lecture seule avec un rôle PostgreSQL limité ;
- agent obligé d'appeler les outils avant de répondre ;
- aucune quantité, aucun prix et aucune succursale ne doivent être inventés ;
- REST choisi parce que les questions sont indépendantes.

### 6. Démonstration — 4 minutes

Préparer les onglets avant de commencer :

1. Backoffice connecté comme employé ;
2. Backoffice connecté comme admin dans une fenêtre privée ;
3. Client Web ;
4. terminal avec `docker compose ps` et les logs IA.

#### Employé — 1 minute

- montrer sa succursale ;
- ajouter une quantité ;
- retirer une quantité ;
- tenter un retrait supérieur au stock ;
- expliquer qu'il ne peut pas choisir une autre succursale.

#### Administrateur — 1 minute

- créer un common user ;
- lui affecter une succursale ;
- changer sa succursale ou son mot de passe ;
- le soft-delete ;
- rappeler que l'admin ne peut pas gérer le stock.

#### Client et IA — 2 minutes

Poser deux questions préparées :

1. « Quels produits sont disponibles à Fréjus ? »
2. « Je veux 3 unités du produit 1, 2 unités du produit 3 et 4 unités du
   produit 7. Où dois-je aller ? »

Montrer brièvement les logs afin d'identifier les appels Product MCP et Stock
MCP. Si le quota IA est indisponible, utiliser une vidéo enregistrée de ce même
flux.

### 7. Bilan — 45 secondes

Conclure avec :

- les exigences obligatoires couvertes ;
- les tests automatisés et la validation Compose ;
- les compromis : REST sans streaming, pas de mémoire, algorithme glouton ;
- les améliorations futures : historique de mouvements, audit, rate limiting,
  streaming et déploiement.

## Répartition de parole

| Partie | Intervenant |
| --- | --- |
| problème, architecture, Backoffice et sécurité | Vadim |
| Product MCP et Stock MCP | Madi |
| AI Query Service et grounding | Gwendal |
| Client Web, démonstration publique et conclusion | Adib |

## Checklist avant la démonstration

- [ ] commit final identifié et testé ;
- [ ] `.env` configuré sans afficher les secrets ;
- [ ] quota Groq disponible ;
- [ ] `docker compose up --build -d` exécuté ;
- [ ] tous les services sont `healthy` ;
- [ ] seed de démonstration vérifiée ;
- [ ] comptes de démonstration testés ;
- [ ] deux questions IA répétées une dernière fois ;
- [ ] logs ouverts et nettoyés des anciennes erreurs ;
- [ ] navigateur à un niveau de zoom lisible ;
- [ ] vidéo de secours enregistrée ;
- [ ] aucun mot de passe visible à l'écran.

## Questions techniques probables

### Pourquoi ne pas stocker les produits en base ?

L'API externe est la source de vérité. Dupliquer le catalogue créerait des
données périmées et violerait la séparation imposée par le sujet.

### Pourquoi Argon2 et pas SHA-256 ?

Argon2 est une fonction de stockage de mots de passe volontairement coûteuse en
temps et en mémoire. SHA-256 est trop rapide et facilite les essais massifs.

### Comment empêchez-vous un employé de changer de succursale ?

La couche de services lit la succursale depuis l'utilisateur authentifié. Elle
n'accepte aucun `branch_id` fourni par le formulaire.

### Pourquoi deux MCP ?

Le Product MCP masque l'API externe ; le Stock MCP expose seulement des lectures
contrôlées. Cette séparation permet d'accorder au Stock MCP un compte BDD
strictement limité.

### Pourquoi REST et pas WebSocket ?

Chaque question est indépendante et la réponse n'est pas streamée. REST est
plus simple à développer, tester et diagnostiquer pour ce MVP.

### Comment évitez-vous les hallucinations ?

Le premier tour exige un outil, les données proviennent uniquement des MCP et le
prompt interdit d'inventer. Les cas vides ou indisponibles doivent être annoncés
explicitement.
