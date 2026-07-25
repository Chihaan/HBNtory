"""Tests unitaires de services/users.py."""

import pytest
from argon2 import PasswordHasher

from services.users import (
    create_user,
    soft_delete_user,
    change_password,
    change_branch,
    list_users,
)
from services.errors import (
    UsernameAlreadyUsed,
    AdminProtected,
    UserNotFound,
)
from models import UserRole

ph = PasswordHasher()


def test_create_user_hache_le_mot_de_passe(session, branch):
    user = create_user(session, "alice", "secret-123", branch.id)
    session.commit()
    assert user.role == UserRole.COMMON
    assert user.password_hash != "secret-123"
    assert ph.verify(user.password_hash, "secret-123")


def test_create_user_nom_deja_pris(session, branch):
    create_user(session, "alice", "pw1", branch.id)
    session.commit()
    with pytest.raises(UsernameAlreadyUsed):
        create_user(session, "alice", "pw2", branch.id)


def test_soft_delete_marque_deleted_at(session, employee):
    assert employee.deleted_at is None
    soft_delete_user(session, employee.id)
    session.commit()
    assert employee.deleted_at is not None


def test_soft_delete_admin_protege(session, admin):
    with pytest.raises(AdminProtected):
        soft_delete_user(session, admin.id)


def test_soft_delete_inexistant(session):
    with pytest.raises(UserNotFound):
        soft_delete_user(session, 4242)


def test_soft_delete_idempotent(session, employee):
    soft_delete_user(session, employee.id)
    session.commit()
    premier = employee.deleted_at
    soft_delete_user(session, employee.id)
    session.commit()
    assert employee.deleted_at == premier


def test_change_password_remplace_le_hash(session, employee):
    ancien = employee.password_hash
    change_password(session, employee.id, "nouveau-mdp")
    session.commit()
    assert employee.password_hash != ancien
    assert ph.verify(employee.password_hash, "nouveau-mdp")


def test_change_password_inexistant(session):
    with pytest.raises(UserNotFound):
        change_password(session, 4242, "x")


def test_change_password_admin_protege(session, admin):
    with pytest.raises(AdminProtected):
        change_password(session, admin.id, "peu-importe")


def test_change_branch_met_a_jour(session, employee, other_branch):
    change_branch(session, employee.id, other_branch.id)
    session.commit()
    assert employee.branch_id == other_branch.id


def test_change_branch_admin_protege(session, admin, branch):
    with pytest.raises(AdminProtected):
        change_branch(session, admin.id, branch.id)


def test_change_branch_inexistant(session, branch):
    with pytest.raises(UserNotFound):
        change_branch(session, 4242, branch.id)


def test_list_users_supprimes_en_bas(session, branch):
    create_user(session, "carol", "pw", branch.id)
    create_user(session, "alice", "pw", branch.id)
    bob = create_user(session, "bob", "pw", branch.id)
    session.commit()
    soft_delete_user(session, bob.id)
    session.commit()
    noms = [u.username for u in list_users(session)]
    # Vivants triés par nom d'abord, supprimés en dernier
    assert noms == ["alice", "carol", "bob"]
