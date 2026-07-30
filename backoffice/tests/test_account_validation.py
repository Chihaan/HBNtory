"""Tests unitaires de la politique des comptes."""

import pytest

from services.account_validation import (
    normalize_username,
    validate_password,
    validate_username,
)
from services.errors import InvalidUsername, WeakPassword


def test_normalize_username_unicode_et_espaces():
    assert normalize_username("  Ａlice\t  Martin  ") == "Alice Martin"


def test_normalize_username_accepte_none():
    assert normalize_username(None) == ""


@pytest.mark.parametrize("username", ["ab", "---", "a" * 51])
def test_validate_username_refuse_les_valeurs_invalides(username):
    with pytest.raises(InvalidUsername):
        validate_username(username)


def test_validate_username_accepte_un_nom_valide():
    validate_username("Alice Martin")


@pytest.mark.parametrize("password", ["court", " " * 8, "a" * 129])
def test_validate_password_refuse_les_valeurs_invalides(password):
    with pytest.raises(WeakPassword):
        validate_password(password)


def test_validate_password_accepte_un_mot_de_passe_valide():
    validate_password("secret-123")
