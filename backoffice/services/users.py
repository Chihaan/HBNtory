from sqlalchemy import select

from models import User


def list_users(session) -> list[User]:
    """Retourne tous les utilisateurs, triés par nom."""
    users = session.execute(
        select(User)
        .order_by(User.username)
    ).scalars().all()
    return users
