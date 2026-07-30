# Client Web HBNtory

Interface publique permettant d'interroger les produits et les stocks en
langage naturel.

## Communication

Le navigateur envoie une requête REST au proxy Nginx :

```http
POST /api/ask
Content-Type: application/json

{"question": "Où trouver trois ordinateurs portables ?"}
```

Nginx transmet la requête à `http://ai-service:8002/ask`. Le navigateur
n'accède directement ni aux MCP, ni à PostgreSQL, ni à l'API produits.

## Lancement

Depuis la racine du dépôt :

```bash
./run-dev.sh
```

L'interface est ensuite disponible sur http://localhost:8080.

## Vérifier le flux complet

La stack étant démarrée, depuis la racine du dépôt :

```bash
./smoke-test.sh
```

Le script contrôle les trois sauts du trajet et sort en erreur si l'un
d'eux est rompu :

1. Nginx sert bien la page (`GET /`) ;
2. Nginx atteint l'AI Service et retire le préfixe (`GET /api/health`
   arrive sur `/health`) ;
3. `POST /api/ask` transmet le corps JSON jusqu'à `POST /ask` — la
   question envoyée dépasse la limite de 1000 caractères, donc seule sa
   traversée complète peut produire l'erreur de validation attendue.

**Aucun quota Groq n'est consommé** : les trois étapes s'arrêtent avant
l'appel au modèle. Pour poser en plus une vraie question (et donc
consommer du quota) : `./smoke-test.sh --avec-ia`.

Le contrat entre les trois couches est aussi vérifié hors Docker par
`ai_service/tests/test_flux_client_web.py`.

## Exemples de questions

- « Donne-moi les détails du produit 12. »
- « Dans quelle succursale le produit 3 est-il disponible ? »
- « Où puis-je acheter trois laptops et deux claviers ? »

## Affichage et messages d'erreur

La réponse est toujours écrite avec `textContent`, jamais avec
`innerHTML` : rien de ce que renvoie le service n'est interprété comme
du HTML. En contrepartie le navigateur n'affiche pas le Markdown, c'est
pourquoi l'agent a pour consigne de répondre en texte brut
(`SYSTEM_PROMPT` dans `ai_service/agent.py`).

Les cas d'échec affichent tous une phrase en français :

| Situation | Message |
| --- | --- |
| Limite temporaire Groq (429) | « … Réessayez dans une minute. » |
| Erreur du service avec `detail` texte (503, 504) | le `detail` renvoyé |
| Erreur de validation (422, `detail` tableau Pydantic) | « Question refusée : … » |
| Réponse non JSON, ex. page 502 de Nginx | « … erreur (code 502). » |
| Requête impossible à envoyer (service ou réseau coupé) | « Impossible de contacter le service… » |
| Aucune réponse dans les 90 s | « … mis trop de temps à répondre… » |
| Réponse JSON sans champ `answer` exploitable | « Le service n'a retourné aucune réponse. » |

### Contrôle manuel

Le client web n'a pas d'outillage de test JavaScript ; ces cas se
vérifient à la main, l'interface ouverte sur http://localhost:8080.

1. **Erreur de validation** : coller une question de plus de 1000
   caractères et envoyer. L'AI Service répond 422 avec un tableau
   Pydantic, l'interface doit afficher « Question refusée : … » et non
   « [object Object] ».
2. **Service arrêté** : `docker compose stop ai-service`, puis poser une
   question. Nginx renvoie une page 502 qui n'est pas du JSON :
   l'interface doit afficher le message citant le code 502.
3. **Requête impossible** : `docker compose stop client-web` sans
   recharger la page, puis envoyer. `fetch` échoue avant d'obtenir une
   réponse : l'interface doit afficher « Impossible de contacter le
   service d'assistance. »
4. Dans les trois cas, le bouton doit redevenir cliquable et l'indicateur
   « Recherche… » disparaître.

Ne pas oublier `docker compose start ai-service client-web` ensuite.
