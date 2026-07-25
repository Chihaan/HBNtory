from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from models import User

ph = PasswordHasher()

# Hash bidon calculé une fois, réutilisé pour égaliser le temps de
# réponse quand l'identifiant n'existe pas (anti-énumération par timing).
_DUMMY_HASH = ph.hash("dummy-password-anti-enumeration")


def check_password(user: User, password: str) -> bool:
    """Vérifie le mot de passe saisi contre le hash de l'utilisateur.

    Retourne True si le mot de passe correspond, False sinon.
    """
    try:
        return ph.verify(user.password_hash, password)
    except VerifyMismatchError:
        return False


def waste_time() -> None:
    """Consomme un temps de vérif Argon2 sans utilisateur réel.

    Appelée quand l'identifiant est inconnu/désactivé pour que la
    réponse prenne le même temps qu'un identifiant valide, empêchant
    de deviner quels comptes existent en mesurant la latence.
    """
    try:
        ph.verify(_DUMMY_HASH, "wrong")
    except VerifyMismatchError:
        pass
