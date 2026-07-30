from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from argon2 import PasswordHasher

from models import User, UserRole
from services.errors import (
    UsernameAlreadyUsed,
    AdminProtected,
    UserNotFound
)
from services.account_validation import (
    normalize_username,
    validate_password,
    validate_username
)

ph = PasswordHasher()


def _is_username_collision(exc: IntegrityError) -> bool:
    """Reconnaît la contrainte unique du nom selon PostgreSQL ou SQLite."""
    diagnostic = getattr(exc.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    if constraint_name == "users_username_key":
        return True

    message = str(exc.orig).lower()
    return (
        "unique constraint failed" in message
        and "users.username" in message
    )


def list_users(session) -> list[User]:
    """Retourne tous les utilisateurs, triés par nom."""
    users = session.execute(
        select(User)
        .order_by(User.deleted_at.is_not(None), User.username)
    ).scalars().all()
    return users


def create_user(
        session,
        username: str,
        password: str,
        branch_id: int
        ) -> User:
    """Crée un common user avec mot de passe haché. Lève si le nom est pris."""
    username = normalize_username(username)
    validate_username(username)
    validate_password(password)
    user = session.execute(
        select(User)
        .where(User.username == username)
    ).scalar_one_or_none()

    if user is not None:
        raise UsernameAlreadyUsed(
            "Ce nom d'utilisateur est déjà pris."
        )

    password_hash = ph.hash(password)
    user = User(
        username=username,
        password_hash=password_hash,
        role=UserRole.COMMON,
        branch_id=branch_id,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if _is_username_collision(exc):
            raise UsernameAlreadyUsed(
                "Ce nom d'utilisateur est déjà pris."
            ) from exc
        raise

    return user


def soft_delete_user(session, user_id: int) -> User:
    """Soft-delete un common user (deleted_at). Refuse un admin."""
    user = session.execute(
        select(User)
        .where(User.id == user_id)
    ).scalar_one_or_none()

    if user is None:
        raise UserNotFound(
            "L'utilisateur n'existe pas."
        )

    if user.role == UserRole.ADMIN:
        raise AdminProtected(
            "Suppression impossible sur l'administrateur."
        )

    if user.deleted_at is not None:
        return user

    user.deleted_at = datetime.now(timezone.utc)
    return user


def change_password(session, user_id: int, new_password: str) -> User:
    """Remplace le mot de passe d'un utilisateur (haché)."""
    user = session.execute(
        select(User)
        .where(User.id == user_id)
    ).scalar_one_or_none()

    if user is None:
        raise UserNotFound(
            "L'utilisateur n'existe pas."
        )

    if user.role == UserRole.ADMIN:
        raise AdminProtected(
            "Le mot de passe de l'administrateur ne peut pas être modifié."
        )

    validate_password(new_password)
    user.password_hash = ph.hash(new_password)
    return user


def change_branch(session, user_id: int, branch_id: int) -> User:
    """Change la succursale d'un utilisateur"""
    user = session.execute(
        select(User)
        .where(User.id == user_id)
    ).scalar_one_or_none()

    if user is None:
        raise UserNotFound(
            "L'utilisateur n'existe pas."
        )

    if user.role == UserRole.ADMIN:
        raise AdminProtected(
            "La succursale de l'administrateur ne peut pas être modifiée."
        )

    user.branch_id = branch_id
    return user


def set_active(session, user_id: int, active: bool) -> User:
    """Active ou désactive un utilisateur (refuse l'admin).

    Distinct du soft-delete : un compte désactivé est suspendu mais
    reste réactivable. Le login refuse déjà les comptes inactifs.
    """
    user = session.execute(
        select(User)
        .where(User.id == user_id)
    ).scalar_one_or_none()

    if user is None:
        raise UserNotFound(
            "L'utilisateur n'existe pas."
        )

    if user.role == UserRole.ADMIN:
        raise AdminProtected(
            "L'administrateur ne peut pas être désactivé."
        )

    user.is_active = active
    return user
