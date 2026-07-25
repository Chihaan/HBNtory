"""Tests unitaires de services/auth.py."""

from argon2 import PasswordHasher

from services.auth import check_password
from models import User, UserRole

ph = PasswordHasher()


def _user(password):
    return User(
        username="x",
        password_hash=ph.hash(password),
        role=UserRole.COMMON,
        branch_id=1,
    )


def test_check_password_correct():
    user = _user("bon-mdp")
    assert check_password(user, "bon-mdp") is True


def test_check_password_incorrect():
    user = _user("bon-mdp")
    assert check_password(user, "mauvais-mdp") is False
