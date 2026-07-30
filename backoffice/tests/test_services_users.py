"""Tests unitaires de services/users.py."""

import pytest
from argon2 import PasswordHasher
from sqlalchemy.exc import IntegrityError

import services.users as users_service
from services.users import (
    create_user,
    soft_delete_user,
    change_password,
    change_branch,
    set_active,
    list_users,
)
from services.errors import (
    UsernameAlreadyUsed,
    AdminProtected,
    InvalidUsername,
    UserNotFound,
    WeakPassword,
)
from models import UserRole

ph = PasswordHasher()


class _EmptyResult:
    def scalar_one_or_none(self):
        return None


class _FastHasher:
    @staticmethod
    def hash(value):
        return "hash"


class _FailingFlushSession:
    def __init__(self, error):
        self.error = error
        self.rolled_back = False

    def execute(self, statement):
        return _EmptyResult()

    def add(self, user):
        pass

    def flush(self):
        raise self.error

    def rollback(self):
        self.rolled_back = True


def test_create_user_hache_le_mot_de_passe(session, branch):
    user = create_user(session, "alice", "secret-123", branch.id)
    session.commit()
    assert user.role == UserRole.COMMON
    assert user.password_hash != "secret-123"
    assert ph.verify(user.password_hash, "secret-123")


def test_create_user_nom_deja_pris(session, branch):
    create_user(session, "alice", "valid-pw1", branch.id)
    session.commit()
    with pytest.raises(UsernameAlreadyUsed):
        create_user(session, "alice", "valid-pw2", branch.id)


def test_create_user_traduit_une_collision_concurrente(monkeypatch):
    error = IntegrityError(
        "INSERT", {}, Exception(
            "UNIQUE constraint failed: users.username"
        )
    )
    failing_session = _FailingFlushSession(error)
    monkeypatch.setattr(users_service, "ph", _FastHasher())

    with pytest.raises(UsernameAlreadyUsed):
        create_user(failing_session, "alice", "valid-pass", 1)

    assert failing_session.rolled_back is True


def test_create_user_ne_masque_pas_une_autre_erreur_integrite(monkeypatch):
    error = IntegrityError(
        "INSERT", {}, Exception("FOREIGN KEY constraint failed")
    )
    failing_session = _FailingFlushSession(error)
    monkeypatch.setattr(users_service, "ph", _FastHasher())

    with pytest.raises(IntegrityError) as captured:
        create_user(failing_session, "alice", "valid-pass", 999)

    assert captured.value is error
    assert failing_session.rolled_back is True


def test_create_user_normalise_le_nom(session, branch):
    user = create_user(session, "  Ａlice   Martin  ", "secret-123", branch.id)
    session.commit()
    assert user.username == "Alice Martin"


@pytest.mark.parametrize("username", ["ab", "---", "a" * 51])
def test_create_user_refuse_un_nom_invalide(session, branch, username):
    with pytest.raises(InvalidUsername):
        create_user(session, username, "secret-123", branch.id)


@pytest.mark.parametrize("password", ["court", " " * 8, "a" * 129])
def test_create_user_refuse_un_mot_de_passe_invalide(
        session, branch, password):
    with pytest.raises(WeakPassword):
        create_user(session, "alice", password, branch.id)


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


def test_change_password_refuse_un_mot_de_passe_faible(session, employee):
    ancien = employee.password_hash
    with pytest.raises(WeakPassword):
        change_password(session, employee.id, "court")
    assert employee.password_hash == ancien


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


def test_set_active_desactive(session, employee):
    assert employee.is_active is True
    set_active(session, employee.id, False)
    session.commit()
    assert employee.is_active is False


def test_set_active_reactive(session, employee):
    set_active(session, employee.id, False)
    session.commit()
    set_active(session, employee.id, True)
    session.commit()
    assert employee.is_active is True


def test_set_active_admin_protege(session, admin):
    with pytest.raises(AdminProtected):
        set_active(session, admin.id, False)


def test_set_active_inexistant(session):
    with pytest.raises(UserNotFound):
        set_active(session, 4242, False)


def test_list_users_supprimes_en_bas(session, branch):
    create_user(session, "carol", "valid-pw", branch.id)
    create_user(session, "alice", "valid-pw", branch.id)
    bob = create_user(session, "bob", "valid-pw", branch.id)
    session.commit()
    soft_delete_user(session, bob.id)
    session.commit()
    noms = [u.username for u in list_users(session)]
    # Vivants triés par nom d'abord, supprimés en dernier
    assert noms == ["alice", "carol", "bob"]
