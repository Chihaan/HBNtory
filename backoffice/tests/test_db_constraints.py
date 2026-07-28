"""Tests des contraintes de base (défense en profondeur).

On vérifie que la base REJETTE elle-même les données incohérentes,
indépendamment de la logique applicative.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from models import (
    Branch, MAX_STOCK_QUANTITY, Stock, User, UserRole
)

HASH = "x"  # peu importe pour tester les contraintes


def test_username_unique(session, branch):
    session.add(User(username="dup", password_hash=HASH,
                     role=UserRole.COMMON, branch_id=branch.id))
    session.flush()
    session.add(User(username="dup", password_hash=HASH,
                     role=UserRole.COMMON, branch_id=branch.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_branch_name_unique(session, branch):
    session.add(Branch(name="Fréjus Centre", city="Ailleurs"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_stock_branch_product_unique(session, branch):
    session.add(Stock(branch_id=branch.id, product_id=1, quantity=5))
    session.flush()
    session.add(Stock(branch_id=branch.id, product_id=1, quantity=9))
    with pytest.raises(IntegrityError):
        session.flush()


def test_stock_quantity_non_negative(session, branch):
    session.add(Stock(branch_id=branch.id, product_id=2, quantity=-1))
    with pytest.raises(IntegrityError):
        session.flush()


def test_stock_quantity_ne_depasse_pas_le_maximum(session, branch):
    session.add(Stock(
        branch_id=branch.id,
        product_id=2,
        quantity=MAX_STOCK_QUANTITY + 1,
    ))
    with pytest.raises(IntegrityError):
        session.flush()


def test_common_sans_succursale_refuse(session):
    session.add(User(username="orphelin", password_hash=HASH,
                     role=UserRole.COMMON, branch_id=None))
    with pytest.raises(IntegrityError):
        session.flush()


def test_admin_avec_succursale_refuse(session, branch):
    session.add(User(username="chef", password_hash=HASH,
                     role=UserRole.ADMIN, branch_id=branch.id))
    with pytest.raises(IntegrityError):
        session.flush()
