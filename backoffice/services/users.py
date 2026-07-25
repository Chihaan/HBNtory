from sqlalchemy import select

from argon2 import PasswordHasher

from models import User, UserRole
from services.errors import UsernameAlreadyUsed

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
