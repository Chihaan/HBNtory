# Guide Docker - HBNtory

Ce document couvre l'installation, l'usage quotidien et le dépannage de la
stack Docker. Pour une vue d'ensemble du projet, voir le
[README](../README.md).

## Prérequis

Docker installé et **lancé** (Docker Desktop ou OrbStack). Vérifier :

```bash
docker ps
```

Un tableau vide avec des en-têtes, c'est bon. Une erreur de connexion
signifie que l'application Docker n'est pas démarrée.

## Première installation

```bash
# 1. Créer son fichier de configuration personnel
cp .env.exemple .env
```

Ouvrir ensuite `.env` et remplacer les valeurs à générer :

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"      # SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"  # MCP_DB_PASSWORD
```

Deux points d'attention :

- `MCP_DB_PASSWORD` apparaît **deux fois** dans le fichier (la variable
  elle-même, puis à l'intérieur de `MCP_DATABASE_URL`). Les deux valeurs
  doivent être identiques, sinon le Stock MCP Server ne pourra pas se
  connecter.
- `GEMINI_API_KEY` doit contenir une clé valide, obtenue sur
  [Google AI Studio](https://aistudio.google.com/apikey). Sans elle, toute
  la stack démarre mais l'AI Query Service échoue à chaque question.

Puis lancer l'ensemble :

```bash
./run-dev.sh
```

Ce script démarre les 7 services, attend que la base soit prête, crée les
tables, configure le rôle en lecture seule et insère les données de
démonstration. Il est **idempotent** : le relancer ne duplique rien.

## Vérifier que tout marche

```bash
docker compose ps                                   # 7 services "running"
curl http://localhost:5001/health                   # API produits
curl http://localhost:8000/login -o /dev/null -s -w '%{http_code}\n'
curl http://localhost:8080 -o /dev/null -s -w '%{http_code}\n'
```

Test de la chaîne IA complète :

```bash
curl -s -X POST http://localhost:8002/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Quelles succursales avez-vous ?"}'
```

Pour inspecter la base :

```bash
docker compose exec db psql -U hbntory -d hbntory
```

```sql
\dt                          -- lister les tables
SELECT * FROM branches;      -- les succursales et leurs identifiants
\q                           -- quitter
```

## Les 7 services

| Service | Port hôte | Port interne | Rôle |
|---|---|---|---|
| `db` | 5432 | 5432 | PostgreSQL 16 |
| `external-products-api` | 5001 | 5000 | API produits fournie par Holberton |
| `backoffice` | 8000 | 8000 | Application interne authentifiée |
| `mcp-server` | 8001 | 8001 | Product MCP Server |
| `ai-service` | 8002 | 8002 | AI Query Service (FastAPI + Gemini) |
| `stock-mcp-server` | 8003 | 8003 | Stock MCP Server |
| `client-web` | 8080 | 80 | Client Web public (nginx) |

Depuis un conteneur, on s'adresse aux autres par **nom de service et port
interne** : `http://external-products-api:5000`, `db:5432`,
`http://mcp-server:8001/mcp`.

> `localhost` à l'intérieur d'un conteneur désigne **le conteneur
> lui-même**, pas la machine hôte. Dans le code et dans `.env`, on utilise
> toujours le nom du service.

## Au quotidien

```bash
docker compose up -d        # démarrer
docker compose down         # arrêter (les données sont conservées)
docker compose logs -f ai-service   # suivre les logs d'un service
```

**Quand faut-il relancer quoi ?**

| J'ai modifié… | Je fais… |
|---|---|
| Un fichier `.py`, `.html`, `.css`, `.js` | **Rien** : les sources sont montées en volume |
| Un `requirements.txt` ou un `Dockerfile` | `docker compose up -d --build <service>` |
| Le `docker-compose.yml` ou le `.env` | `docker compose up -d` |
| `models.py` (schéma de la base) | `docker compose run --rm backoffice python init_db.py` |

Le montage en volume a une conséquence importante : **changer de branche
git change le code exécuté** sans reconstruire l'image. En revanche, si les
dépendances diffèrent d'une branche à l'autre, l'image reste celle de la
branche précédente et il faut reconstruire. C'est la cause typique d'un
`ModuleNotFoundError` inexplicable.

## Les fichiers utilisés

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | Les 7 services et leurs dépendances |
| `.env` | **Ta** configuration locale. Jamais commité. |
| `.env.exemple` | Le modèle à copier. Commité. |
| `run-dev.sh` | Démarre la stack et initialise la base |
| `backoffice/docker-entrypoint.sh` | Attend la base, puis lance `bootstrap.py` |
| `backoffice/init_db.py` | Crée les tables et le rôle `mcp_reader` |
| `backoffice/bootstrap.py` | Initialisation idempotente au démarrage |
| `backoffice/seed.py` | Données de démonstration |
| `external/product-api/` | API fournie par Holberton. **On n'y touche pas.** |

## Comptes de démonstration

| Identifiant | Rôle | Succursale | Mot de passe |
|---|---|---|---|
| `admin` | Administrateur | aucune | `ADMIN_PASSWORD` (défaut `ChangeMe123!`) |
| `marie` | Employée | Fréjus Centre | `SEED_USER_PASSWORD` (défaut `Test123!`) |
| `paul` | Employé | Laval Gare | `SEED_USER_PASSWORD` (défaut `Test123!`) |

## Quand ça ne marche pas

**Toujours commencer par les logs**, jamais par une recherche web :

```bash
docker compose ps            # qui tourne, qui a planté
docker compose logs db       # pourquoi
```

| Message | Cause | Solution |
|---|---|---|
| `.env: no such file` | Le `.env` n'a pas été créé | `cp .env.exemple .env` |
| `port is already allocated` | Un ancien conteneur tourne encore | `docker compose down` puis relancer |
| `connection refused` vers la base | La base n'était pas prête | `docker compose ps`, puis les logs |
| `ModuleNotFoundError` | Dépendance ajoutée sans reconstruction | `docker compose up -d --build <service>` |
| `password authentication failed` | Mots de passe incohérents dans `.env` | Vérifier les **deux** occurrences de `MCP_DB_PASSWORD` |
| `KeyError: 'MCP_SERVER_URL'` | Variable absente du `.env` | Comparer avec `.env.exemple` |
| HTTP 500 sur `/ask` | Clé Gemini absente, invalide, ou quota dépassé | `docker compose logs ai-service` |
| L'agent répond mais sans données | Un serveur MCP est injoignable | Vérifier `mcp-server` et `stock-mcp-server` |

### Une réponse ne correspond pas au code

Symptôme : le code a été modifié, mais le service se comporte comme avant,
ou une trace d'erreur cite un numéro de ligne qui n'existe pas dans le
fichier.

Le processus tourne encore avec l'ancien code chargé en mémoire :

```bash
docker compose restart ai-service          # recharger le code
docker compose up -d --build ai-service    # si les dépendances ont changé
```

### Repartir de zéro

```bash
docker compose down -v      # ATTENTION : efface AUSSI la base de données
./run-dev.sh
```

Le `-v` supprime le volume PostgreSQL. Les données de démonstration seront
recréées, mais **les identifiants de succursale changeront** (la séquence
PostgreSQL ne repart pas de 1 si le volume est réutilisé, et repart de 1
s'il est supprimé). C'est pourquoi aucun script ne doit fixer un
`branch_id` en dur.

## Documents liés

- [README](../README.md) - installation et vue d'ensemble
- [`architecture.md`](architecture.md) - pourquoi ce découpage en services
- [`database.md`](database.md) - schéma et initialisation
- [`testing.md`](testing.md) - comment lancer les tests
