"""Tests de la seed de démonstration non destructive."""

import pytest
from sqlalchemy import func, select

import seed as seed_module
from models import Branch, Stock, User, UserRole


def _count(session, model):
    return session.execute(select(func.count(model.id))).scalar_one()


def _stock_quantity(session, branch_id, product_id):
    return session.execute(
        select(Stock.quantity)
        .where(Stock.branch_id == branch_id)
        .where(Stock.product_id == product_id)
    ).scalar_one()


def _branch(session, name):
    return session.execute(
        select(Branch).where(Branch.name == name)
    ).scalar_one()


def _expected_stock_count():
    return sum(len(items) for items in seed_module.STOCK.values())


def test_seed_base_vide_cree_toute_la_demo(session):
    stats = seed_module.seed(session)
    session.commit()

    assert stats["branches_created"] == len(seed_module.BRANCHES)
    assert stats["users_created"] == len(seed_module.COMMON_USERS) + 1
    assert stats["stock_created"] == _expected_stock_count()
    assert _count(session, Branch) == len(seed_module.BRANCHES)
    assert _count(session, User) == len(seed_module.COMMON_USERS) + 1
    assert _count(session, Stock) == _expected_stock_count()

    for branch_name, items in seed_module.STOCK.items():
        branch = _branch(session, branch_name)
        for product_id, quantity in items.items():
            assert _stock_quantity(
                session, branch.id, product_id
            ) == quantity


@pytest.mark.parametrize(
    ("product_id", "quantity"),
    [
        pytest.param(1, 0, id="zero"),
        pytest.param(3, 99, id="superieure"),
        pytest.param(7, 1, id="inferieure"),
    ],
)
def test_seed_preserve_toute_quantite_existante(
        session, product_id, quantity):
    branch = Branch(name="Fréjus Centre", city="Fréjus")
    session.add(branch)
    session.flush()
    session.add(Stock(
        branch=branch,
        product_id=product_id,
        quantity=quantity,
    ))
    session.commit()

    seed_module.seed(session)
    session.commit()

    assert _stock_quantity(
        session, branch.id, product_id
    ) == quantity


def test_seed_base_partielle_preserve_et_complete_toutes_les_succursales(
        session):
    branch = Branch(
        name=seed_module.DEMO_BRANCH_NAME,
        city="Ville personnalisée",
        is_active=False,
    )
    session.add(branch)
    session.flush()
    custom_user = User(
        username="marie",
        password_hash="hash-existant",
        role=UserRole.COMMON,
        branch=branch,
    )
    session.add(custom_user)
    session.add_all([
        Stock(branch=branch, product_id=1, quantity=1),
        Stock(branch=branch, product_id=999, quantity=17),
    ])
    session.commit()

    stats = seed_module.seed(session)
    session.commit()

    preserved_user = session.execute(
        select(User).where(User.username == "marie")
    ).scalar_one()
    assert preserved_user.password_hash == "hash-existant"
    assert preserved_user.role == UserRole.COMMON
    assert preserved_user.branch_id == branch.id
    assert branch.city == "Ville personnalisée"
    assert branch.is_active is False
    assert _stock_quantity(session, branch.id, 1) == 1
    assert _stock_quantity(session, branch.id, 999) == 17
    assert _stock_quantity(session, branch.id, 2) == (
        seed_module.STOCK[branch.name][2]
    )

    laval = _branch(session, "Laval Gare")
    toulouse = _branch(session, "Toulouse Capitole")
    assert _stock_quantity(session, laval.id, 15) == 0
    assert _stock_quantity(session, toulouse.id, 38) == 9
    assert stats["stock_increased"] == 0


def test_seed_est_idempotente(session):
    seed_module.seed(session)
    session.commit()

    second_run = seed_module.seed(session)
    session.commit()
    third_run = seed_module.seed(session)
    session.commit()

    no_change = {
        "branches_created": 0,
        "users_created": 0,
        "stock_created": 0,
        "stock_increased": 0,
    }
    assert second_run == no_change
    assert third_run == no_change


def test_seed_base_vide_cree_admin_et_plusieurs_succursales(session):
    """Le minimum démontrable : un admin et au moins deux succursales."""
    seed_module.seed(session)
    session.commit()

    admin = session.execute(
        select(User).where(User.username == seed_module.ADMIN_USERNAME)
    ).scalar_one()

    assert admin.role == UserRole.ADMIN
    assert _count(session, Branch) >= 2


def test_seed_complete_une_base_sans_succursale(session):
    """Un admin seul, sans succursale ni stock : le reste est créé.

    C'est le cas qu'un simple test « la base contient-elle un
    utilisateur ? » laissait passer, alors que la démonstration y est
    inutilisable. Le mot de passe de l'admin déjà présent n'est pas
    retouché. Toutes les lignes de stock de démonstration manquantes
    sont ajoutées, y compris dans les autres succursales.
    """
    session.add(User(
        username=seed_module.ADMIN_USERNAME,
        password_hash="hash-existant",
        role=UserRole.ADMIN,
    ))
    session.commit()

    stats = seed_module.seed(session)
    session.commit()

    demo = session.execute(
        select(Branch).where(Branch.name == seed_module.DEMO_BRANCH_NAME)
    ).scalar_one()
    admin = session.execute(
        select(User).where(User.username == seed_module.ADMIN_USERNAME)
    ).scalar_one()

    assert _count(session, Branch) == len(seed_module.BRANCHES)
    assert _count(session, Stock) == _expected_stock_count()
    assert stats["users_created"] == len(seed_module.COMMON_USERS)
    assert stats["stock_created"] == _expected_stock_count()
    assert admin.password_hash == "hash-existant"
    assert _stock_quantity(session, demo.id, 1) == (
        seed_module.STOCK[seed_module.DEMO_BRANCH_NAME][1]
    )
    laval = _branch(session, "Laval Gare")
    toulouse = _branch(session, "Toulouse Capitole")
    assert _stock_quantity(session, laval.id, 21) == 6
    assert _stock_quantity(session, toulouse.id, 38) == 9


def test_seed_trois_executions_ne_dupliquent_aucune_ligne(session):
    """Compte réellement les lignes, pas seulement les compteurs."""
    seed_module.seed(session)
    session.commit()
    attendu = (
        _count(session, Branch),
        _count(session, User),
        _count(session, Stock),
    )

    for _ in range(2):
        seed_module.seed(session)
        session.commit()

    assert (
        _count(session, Branch),
        _count(session, User),
        _count(session, Stock),
    ) == attendu


def test_reset_explicite_reconstruit_toute_la_demo(session, capsys):
    seed_module.seed(session)
    demo = _branch(session, seed_module.DEMO_BRANCH_NAME)
    stock = session.execute(
        select(Stock)
        .where(Stock.branch_id == demo.id)
        .where(Stock.product_id == 1)
    ).scalar_one()
    stock.quantity = 0
    session.add(Branch(name="Donnée à supprimer", city="Test"))
    session.commit()

    seed_module.main(reset=True)
    capsys.readouterr()
    session.expire_all()

    assert session.execute(
        select(Branch).where(Branch.name == "Donnée à supprimer")
    ).scalar_one_or_none() is None
    rebuilt_demo = _branch(session, seed_module.DEMO_BRANCH_NAME)
    assert _stock_quantity(session, rebuilt_demo.id, 1) == (
        seed_module.STOCK[seed_module.DEMO_BRANCH_NAME][1]
    )
    assert _count(session, Stock) == _expected_stock_count()


def test_seed_refuse_une_succursale_inconnue(session, monkeypatch):
    """Un nom mal orthographié donne une erreur lisible, pas un KeyError."""
    monkeypatch.setattr(
        seed_module,
        "STOCK",
        {"Succursale Fantôme": {1: 5}},
    )

    with pytest.raises(ValueError, match="Succursale Fantôme"):
        seed_module.seed(session)


def test_seed_refuse_une_demo_a_une_seule_succursale(session, monkeypatch):
    """La démo multi-succursales n'a pas de sens avec une seule adresse."""
    monkeypatch.setattr(
        seed_module,
        "BRANCHES",
        [{"name": seed_module.DEMO_BRANCH_NAME, "city": "Fréjus"}],
    )

    with pytest.raises(ValueError, match="deux succursales"):
        seed_module.seed(session)
