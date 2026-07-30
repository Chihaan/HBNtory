"""Tests du bootstrap partagé par Docker et le lancement local."""

from sqlalchemy import func, select

import bootstrap
from db import SessionLocal
from models import Branch, User, UserRole


def _sans_postgres(monkeypatch, calls):
    """Neutralise les deux étapes qui exigent un vrai PostgreSQL."""
    monkeypatch.setattr(bootstrap, "create_tables",
                        lambda: calls.append("tables"))
    monkeypatch.setattr(bootstrap, "configure_readonly_role",
                        lambda: calls.append("permissions"))


def test_bootstrap_prepare_le_schema_avant_la_seed(monkeypatch):
    """Les tables et le rôle lecture seule précèdent la seed."""
    calls = []
    _sans_postgres(monkeypatch, calls)
    monkeypatch.setattr(bootstrap, "seed_database",
                        lambda: calls.append("seed"))

    bootstrap.main()

    assert calls == ["tables", "permissions", "seed"]


def test_bootstrap_complete_une_base_deja_peuplee(monkeypatch):
    """Une base incomplète est complétée, sans écraser l'existant.

    Cas concret : l'admin existe déjà mais aucune succursale n'a été
    créée. La seed doit quand même s'exécuter, sinon la démonstration
    reste inutilisable ; le mot de passe de l'admin n'est pas touché.
    """
    with SessionLocal() as prepare:
        prepare.add(User(
            username="admin",
            password_hash="hash-existant",
            role=UserRole.ADMIN,
        ))
        prepare.commit()

    _sans_postgres(monkeypatch, [])
    bootstrap.main()

    with SessionLocal() as check:
        assert check.execute(
            select(func.count(Branch.id))
        ).scalar_one() >= 2
        conserve = check.execute(
            select(User).where(User.username == "admin")
        ).scalar_one()
        assert conserve.password_hash == "hash-existant"


def test_bootstrap_relance_ne_duplique_rien(monkeypatch):
    """Deux démarrages successifs laissent la même base."""
    _sans_postgres(monkeypatch, [])
    bootstrap.main()

    with SessionLocal() as check:
        apres_un_demarrage = check.execute(
            select(func.count(User.id))
        ).scalar_one()

    bootstrap.main()

    with SessionLocal() as check:
        assert check.execute(
            select(func.count(User.id))
        ).scalar_one() == apres_un_demarrage
