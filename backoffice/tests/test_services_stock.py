"""Tests unitaires de services/stock.py."""

import pytest

import services.stock as stock_service
from services.stock import add_stock, remove_stock, list_stock
from models import Stock
from services.errors import (
    InvalidStockQuantity,
    InsufficientStock,
    ProductNotFound,
    NoBranchAssigned,
)


def _get_qty(session, branch_id, product_id):
    return session.query(Stock).filter_by(
        branch_id=branch_id, product_id=product_id
    ).one().quantity


def test_add_stock_cree_une_ligne(session, employee, monkeypatch):
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    add_stock(session, employee, 5, 10)
    session.commit()
    assert _get_qty(session, employee.branch_id, 5) == 10


def test_add_stock_incremente_existant(session, employee, monkeypatch):
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    add_stock(session, employee, 5, 10)
    add_stock(session, employee, 5, 4)
    session.commit()
    assert _get_qty(session, employee.branch_id, 5) == 14


def test_add_stock_produit_inconnu(session, employee, monkeypatch):
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: False)
    with pytest.raises(ProductNotFound):
        add_stock(session, employee, 999, 3)


@pytest.mark.parametrize("bad", [0, -1, True, "5", 2.5])
def test_add_stock_quantite_invalide(session, employee, bad):
    with pytest.raises(InvalidStockQuantity):
        add_stock(session, employee, 5, bad)


def test_add_stock_admin_sans_succursale(session, admin, monkeypatch):
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    with pytest.raises(NoBranchAssigned):
        add_stock(session, admin, 5, 10)


def test_remove_stock_decremente(session, employee, monkeypatch):
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    add_stock(session, employee, 5, 10)
    remove_stock(session, employee, 5, 4)
    session.commit()
    assert _get_qty(session, employee.branch_id, 5) == 6


def test_remove_stock_insuffisant(session, employee, monkeypatch):
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    add_stock(session, employee, 5, 3)
    with pytest.raises(InsufficientStock):
        remove_stock(session, employee, 5, 10)


def test_remove_stock_produit_absent(session, employee):
    with pytest.raises(InsufficientStock):
        remove_stock(session, employee, 777, 1)


@pytest.mark.parametrize("bad", [0, -5, False])
def test_remove_stock_quantite_invalide(session, employee, bad):
    with pytest.raises(InvalidStockQuantity):
        remove_stock(session, employee, 5, bad)


def test_list_stock_trie_par_produit(session, employee, monkeypatch):
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    add_stock(session, employee, 8, 1)
    add_stock(session, employee, 2, 1)
    session.commit()
    lignes = list_stock(session, employee)
    assert [ligne.product_id for ligne in lignes] == [2, 8]


def test_list_stock_admin_sans_succursale(session, admin):
    with pytest.raises(NoBranchAssigned):
        list_stock(session, admin)


def test_stock_isole_par_succursale(session, employee, other_branch,
                                    monkeypatch):
    """Un employé n'opère et ne voit QUE sa propre succursale."""
    monkeypatch.setattr(stock_service, "product_exists", lambda pid: True)
    # Stock présent dans une AUTRE succursale
    session.add(Stock(branch_id=other_branch.id, product_id=99, quantity=50))
    session.commit()
    # L'employé ajoute chez lui : aucune route ne permet de viser
    # une autre succursale, l'op est bornée à current_user.branch_id
    add_stock(session, employee, 5, 10)
    session.commit()
    lignes = list_stock(session, employee)
    assert {ligne.product_id for ligne in lignes} == {5}
    assert all(ligne.branch_id == employee.branch_id for ligne in lignes)
