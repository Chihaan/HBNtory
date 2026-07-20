# Convention de commits — HBNtory

## Le format

```
type: description
```

Exemples :

```
feat: ajoute la connexion des utilisateurs
fix: empêche les quantités de stock négatives
docs: rédige le document d'architecture
```

## Les 5 types qu'on utilise

|    Type.   |                     Quand                        |                      Exemple                         |
|------------|--------------------------------------------------|------------------------------------------------------|
|   `feat`   | J'ajoute une fonctionnalité                      | `feat: ajoute le formulaire de retrait de stock`     |
|   `fix`    | Je corrige un bug                                | `fix: corrige le calcul du stock restant`            |
|   `docs`   | Je touche à de la documentation                  | `docs: complète le README`                           |
| `refactor` | Je réorganise du code sans changer ce qu'il fait | `refactor: déplace la logique stock dans un service` |
|   `chore`  | Configuration, dépendances, outillage            | `chore: ajoute le Dockerfile du serveur MCP`         |
