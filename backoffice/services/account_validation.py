import unicodedata

from services.errors import InvalidUsername, WeakPassword

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def normalize_username(value: str | None) -> str:
    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split())


def validate_username(username: str) -> None:
    if not USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH:
        raise InvalidUsername(
            f"Le nom doit contenir entre {USERNAME_MIN_LENGTH} "
            f"et {USERNAME_MAX_LENGTH} caractères."
        )

    if not any(character.isalnum() for character in username):
        raise InvalidUsername(
            "Le nom doit contenir au moins une lettre ou un chiffre."
        )


def validate_password(password: str) -> None:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise WeakPassword(
            f"Le mot de passe doit contenir entre {PASSWORD_MIN_LENGTH} "
            f"et {PASSWORD_MAX_LENGTH} caractères."
        )

    if password.isspace():
        raise WeakPassword(
            "Le mot de passe ne peut pas contenir uniquement des espaces."
        )
