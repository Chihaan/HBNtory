# Utilisation de Docker

## Prérequis

Docker installé et **lancé** (Docker Desktop ou OrbStack). Vérifie :

```bash
docker ps
```

Si tu obtiens un tableau vide avec des en-têtes, c'est bon. Si tu obtiens une erreur de connexion, l'application Docker n'est pas démarrée.

---

## Première installation

```
# 1. Créer ton fichier de configuration personnel
cp .env.exemple .env
```

**Ouvre ensuite `.env` et remplace deux valeurs** par des secrets générés :

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"      # pour SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"  # pour MCP_DB_PASSWORD
```

Le mot de passe MCP apparaît **deux fois** dans le fichier (`MCP_DB_PASSWORD` et à l'intérieur de `MCP_DATABASE_URL`). Les deux doivent être identiques.

```bash
# 3. Démarrer la base de données et l'API produits
docker compose up -d db external-products-api

# 4. Créer les tables
docker compose run --rm backoffice python init_db.py
```

Résultat attendu : `Tables créées : branches, users, stock`

---

## Vérifier que tout marche

```bash
docker compose ps                          # les conteneurs tournent ?
curl http://localhost:5001/health          # l'API produits répond ?
```

Pour regarder la base :

```bash
docker compose exec db psql -U hbntory -d hbntory
```

```sql
\dt          -- liste les tables
\q           -- quitter
```

---

## Au quotidien

```bash
git pull
docker compose up -d db external-products-api    # démarrer
docker compose down                              # arrêter (garde les données)
```

**Quand faut-il relancer quoi ?**

| J'ai modifié… | Je fais… |
|---|---|
| Un fichier `.py`, `.html`, `.css` | **Rien**, c'est pris en compte automatiquement |
| Un `requirements.txt` ou un `Dockerfile` | `docker compose up --build <service>` |
| Le `docker-compose.yml` ou le `.env` | `docker compose up -d` |
| Les modèles (`models.py`) | `docker compose run --rm backoffice python init_db.py` |

---

## Les fichiers utilisés

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | La liste des services et comment ils se parlent |
| `.env` | **Ta** configuration locale. Jamais commité. |
| `.env.exemple` | Le modèle à copier. Commité. |
| `backoffice/Dockerfile` | Comment construire l'image du Backoffice |
| `backoffice/requirements.txt` | Les bibliothèques Python à installer |
| `backoffice/init_db.py` | Crée les tables dans la base |
| `external/product-api/` | L'API fournie par Holberton. **On n'y touche pas.** |

---

## Les adresses

| Service | Depuis ma machine | Depuis un conteneur |
|---|---|---|
| API produits | http://localhost:5001 | `http://external-products-api:5000` |
| PostgreSQL | localhost:5432 | `db:5432` |

> `localhost` à l'intérieur d'un conteneur désigne le conteneur lui-même, pas ta machine. Dans le code, on utilise toujours le **nom du service**.

---

## Quand ça ne marche pas

**Toujours commencer par les logs**, jamais par Google :

```bash
docker compose ps                 # qui tourne, qui a planté
docker compose logs db            # pourquoi
```

| Message | Cause | Solution |
|---|---|---|
| `.env: no such file` | Tu n'as pas créé ton `.env` | `cp .env.exemple .env` |
| `port is already allocated` | Un ancien conteneur tourne encore | `docker compose down` puis relancer |
| `connection refused` vers la base | La base n'était pas prête | `docker compose ps`, puis les logs |
| `ModuleNotFoundError` | Dépendance ajoutée sans reconstruction | `docker compose up --build` |
| `password authentication failed` | Mots de passe incohérents dans `.env` | Vérifier les deux occurrences |

**Si plus rien n'a de sens :**

```bash
docker compose down -v      # ⚠️ efface AUSSI la base de données
docker compose up -d db external-products-api
docker compose run --rm backoffice python init_db.py
```

Signale-le dans le groupe si tu en arrives là.

---

## Note

Les services `mcp-server`, `ai-service` et `client-web` sont déclarés dans le `docker-compose.yml` mais **pas encore écrits**. Un `docker compose up` sans préciser de service échouera donc. Lance uniquement `db` et `external-products-api` pour l'instant.
