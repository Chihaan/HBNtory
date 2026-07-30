# Authentification et autorisation du Backoffice

## Stratégie choisie

Le Backoffice utilise des sessions serveur avec Flask-Login et un cookie de
session signé par Flask.

Ce choix correspond à une application Backoffice rendue côté serveur :

- le navigateur envoie naturellement le cookie à chaque navigation ;
- aucune gestion de jeton JavaScript n'est nécessaire ;
- Flask-Login fournit `login_required`, `current_user` et le rechargement de
  l'utilisateur ;
- toutes les règles restent appliquées côté backend.

La contrepartie est que ce mécanisme est destiné au Backoffice web et non à une
API publique consommée par plusieurs types de clients. Ce compromis est adapté
au périmètre du projet.

## Connexion

Le formulaire `/login` reçoit un nom d'utilisateur et un mot de passe.

Le backend :

1. normalise le nom d'utilisateur ;
2. charge le compte avec SQLAlchemy ;
3. refuse les comptes absents, désactivés ou soft-deleted ;
4. vérifie le mot de passe contre son hash Argon2 ;
5. appelle `login_user()` si les informations sont correctes.

Le même message d'erreur est utilisé pour un compte inconnu et un mauvais mot de
passe. Une vérification Argon2 factice est effectuée lorsque le compte n'existe
pas, afin de limiter l'énumération des identifiants par comparaison de temps de
réponse.

À chaque requête authentifiée, le `user_loader` recharge le compte et vérifie
encore `deleted_at IS NULL` et `is_active = true`. Un utilisateur supprimé ou
désactivé perd donc également l'accès avec une ancienne session.

## Stockage des mots de passe

Les mots de passe sont hachés avec **Argon2** via `argon2-cffi`.

Lors de la création d'un utilisateur ou d'un changement de mot de passe :

```text
mot de passe -> PasswordHasher.hash() -> password_hash en base
```

Lors de la connexion :

```text
mot de passe saisi + hash stocké -> PasswordHasher.verify() -> vrai ou faux
```

Argon2 est conçu pour le stockage de mots de passe. Il utilise un sel et un coût
en temps et en mémoire, ce qui rend les essais massifs plus coûteux.

Un SHA-256 simple n'est pas suffisant : SHA-256 est volontairement rapide. Sans
fonction de dérivation lente et sans paramètres de coût adaptés, un attaquant
ayant obtenu les hashes peut tester un très grand nombre de mots de passe par
seconde. Ajouter manuellement un sel à SHA-256 ne résout pas le problème de
vitesse. Argon2, bcrypt ou PBKDF2 sont conçus pour cet usage ; HBNtory a choisi
Argon2.

Les valeurs `ADMIN_PASSWORD` et `SEED_USER_PASSWORD` ne servent qu'à créer les
comptes absents pendant la seed. Seul leur hash est enregistré dans la base.

## Validation des comptes

Les noms d'utilisateur sont :

- normalisés en Unicode NFKC ;
- débarrassés des espaces superflus ;
- limités à 3–50 caractères ;
- obligés de contenir au moins une lettre ou un chiffre ;
- uniques en base.

Les mots de passe sont limités à 8–128 caractères et ne peuvent pas être
composés uniquement d'espaces.

## Autorisation par rôle

Deux rôles existent :

| Rôle | Autorisé | Interdit |
| --- | --- | --- |
| `ADMIN` | lister, créer, modifier, désactiver et soft-delete les utilisateurs communs | consulter, ajouter ou retirer du stock |
| `COMMON` | consulter et modifier le stock de sa succursale | gérer les utilisateurs ou agir sur une autre succursale |

Les routes utilisent trois niveaux de protection :

1. `@login_required` refuse les utilisateurs anonymes ;
2. `@admin_required` ou `@common_user_required` contrôle le rôle côté serveur ;
3. les services de stock déduisent `branch_id` de `current_user` au lieu
   d'accepter une succursale fournie par le formulaire.

Le navigateur ne peut donc pas choisir une autre succursale en modifiant un
champ caché ou une requête HTTP : ce paramètre n'existe pas dans l'opération de
stock.

La base ajoute une dernière protection en imposant qu'un utilisateur `COMMON`
ait une succursale et qu'un `ADMIN` n'en ait aucune.

## Soft-delete et désactivation

Deux états sont distincts :

- la désactivation place `is_active` à `false` et peut être annulée ;
- le soft-delete renseigne `deleted_at` et conserve l'utilisateur pour la
  traçabilité.

Dans les deux cas, la connexion et le rechargement d'une session sont refusés.
Les lignes de stock ne sont pas affectées, car elles appartiennent aux
succursales.

## Protection de la session et des formulaires

- tous les formulaires mutatifs sont envoyés en `POST` ;
- Flask-WTF fournit un jeton CSRF ;
- le cookie de session est `HttpOnly` et `SameSite=Lax` ;
- l'option `Secure` peut être activée par `SESSION_COOKIE_SECURE=true` quand
  HTTPS est disponible ;
- `SECRET_KEY` doit être une valeur aléatoire locale et ne doit jamais être
  commitée.

SSL/TLS n'est pas requis par le sujet pour l'environnement de démonstration.
