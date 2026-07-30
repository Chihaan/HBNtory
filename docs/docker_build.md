# Utilisation de Docker

## Prérequis

Docker Desktop ou OrbStack doit être installé et démarré :

```bash
docker version
docker compose version
```

## Première installation

Crée la configuration locale :

```bash
cp .env.exemple .env
```

Dans `.env`, remplace au minimum :

- `SECRET_KEY` par une valeur aléatoire ;
- `MCP_DB_PASSWORD` et le mot de passe présent dans `MCP_DATABASE_URL`
  par la même valeur ;
- `GROQ_API_KEY` par la clé fournie à l'équipe.

Les secrets peuvent être générés avec :

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Construis et démarre ensuite tout le projet :

```bash
./run-dev.sh
```

Ou directement avec Compose en arrière-plan :

```bash
docker compose up --build -d
docker compose ps
```

À chaque démarrage, le Backoffice crée les tables manquantes, configure le rôle
MCP en lecture seule et complète les données de démonstration absentes. Les
comptes et quantités déjà présents ne sont pas écrasés.

Pour ajouter ou réparer le scénario de démonstration sur une base existante
sans supprimer les comptes ni diminuer les stocks :

```bash
docker compose exec backoffice python seed.py
```

La commande affiche la question multi-produits prête à copier dans le CWI.
Le mode destructif doit rester explicite :

```bash
docker compose exec backoffice python seed.py --reset
```

## Adresses

| Service | Depuis la machine | Depuis Docker |
|---|---|---|
| Client web | http://localhost:8080 | `http://client-web` |
| Backoffice | http://localhost:8000 | `http://backoffice:8000` |
| AI Service | http://localhost:8002 | `http://ai-service:8002` |
| Product MCP | http://localhost:8001/mcp | `http://mcp-server:8001/mcp` |
| Stock MCP | http://localhost:8003/mcp | `http://stock-mcp-server:8003/mcp` |
| API produits | http://localhost:5001 | `http://external-products-api:5000` |
| PostgreSQL | `localhost:5432` | `db:5432` |

`localhost` dans un conteneur désigne ce conteneur. Les communications
internes utilisent donc toujours les noms de services Docker.

## Vérifications rapides

```bash
curl http://localhost:5001/health
curl http://localhost:8002/health
curl -I http://localhost:8000/login
curl -I http://localhost:8080
docker compose logs --tail=50
```

Test du service IA :

```bash
curl -X POST http://localhost:8002/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Où trouver un ordinateur portable ?"}'
```

## Utilisation quotidienne

```bash
git pull
./run-dev.sh
docker compose down
```

| Modification | Commande |
|---|---|
| Backoffice `.py`, `.html` ou `.css` | Rechargement automatique |
| Code d'un MCP ou de l'AI Service | `docker compose restart <service>` |
| Client web | `docker compose up --build -d client-web` |
| `requirements.txt` ou Dockerfile | `docker compose up --build -d <service>` |
| `docker-compose.yml` ou `.env` | `docker compose up -d` |

## Diagnostic

Commence toujours par identifier le service en erreur :

```bash
docker compose ps
docker compose logs <service>
```

| Message | Vérification |
|---|---|
| `.env: no such file` | Exécuter `cp .env.exemple .env` |
| `port is already allocated` | Arrêter l'ancien service ou conteneur |
| `connection refused` | Regarder les healthchecks avec `docker compose ps` |
| `ModuleNotFoundError` | Reconstruire le service avec `--build` |
| `password authentication failed` | Vérifier les mots de passe de `.env` |
| Réponse IA `429` | Attendre une minute : limite temporaire Groq atteinte |
| Réponse IA `503` | Vérifier `GROQ_API_KEY` et les logs des trois services |

Pour repartir avec une base vide, uniquement si les données peuvent être
perdues :

```bash
docker compose down -v
docker compose up --build -d
```
