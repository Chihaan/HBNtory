"""Tests du bootstrap partagé par Docker et le lancement local."""

import bootstrap


def test_bootstrap_preserve_une_base_existante(monkeypatch):
    """Une base contenant un utilisateur ne doit jamais être reseedée."""
    calls = []
    monkeypatch.setattr(bootstrap, "create_tables",
                        lambda: calls.append("tables"))
    monkeypatch.setattr(bootstrap, "configure_readonly_role",
                        lambda: calls.append("permissions"))
    monkeypatch.setattr(bootstrap, "has_users", lambda: True)
    monkeypatch.setattr(bootstrap, "seed_database",
                        lambda: calls.append("seed"))

    bootstrap.main()

    assert calls == ["tables", "permissions"]


def test_bootstrap_seed_une_base_vide(monkeypatch):
    """Une base sans utilisateur reçoit les données de démonstration."""
    calls = []
    monkeypatch.setattr(bootstrap, "create_tables",
                        lambda: calls.append("tables"))
    monkeypatch.setattr(bootstrap, "configure_readonly_role",
                        lambda: calls.append("permissions"))
    monkeypatch.setattr(bootstrap, "has_users", lambda: False)
    monkeypatch.setattr(bootstrap, "seed_database",
                        lambda: calls.append("seed"))

    bootstrap.main()

    assert calls == ["tables", "permissions", "seed"]
