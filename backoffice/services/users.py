from datetime import datetime, timezone

from sqlalchemy import select

from argon2 import PasswordHasher

from models import User, UserRole
from services.errors import (
    UsernameAlreadyUsed,
    AdminProtected,
    UserNotFound
)

ph = PasswordHasher()


def list_users(session) -> list[User]:
    """Retourne tous les utilisateurs, triés par nom."""
    users = session.execute(
        select(User)
        .order_by(User.username)
    ).scalars().all()
    return users


def create_user(
        session,
        username: str,
        password: str,
        branch_id: int
        ) -> User:
    """Crée un common user avec mot de passe haché. Lève si le nom est pris."""
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

    user.password_hash = ph.hash(new_password)
    return user
