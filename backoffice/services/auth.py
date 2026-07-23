from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from models import User


def check_password(user: User, password: str) -> bool:
    """Vérifie le mot de passe saisi contre le hash de l'utilisateur.

    Retourne True si le mot de passe correspond, False sinon.
    """
    ph = PasswordHasher()
    try:
        return ph.verify(user.password_hash, password)
    except VerifyMismatchError:
        return False

