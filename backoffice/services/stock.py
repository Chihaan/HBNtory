from sqlalchemy import select

from models import Stock
from services.errors import (
    InvalidStockQuantity,
    InsufficientStock,
    ProductNotFound,
    NoBranchAssigned
)
from services.products import product_exists


def _user_branch_id(user):
    """Retourne la succursale de l'utilisateur.

    Lève NoBranchAssigned si l'utilisateur n'en a aucune : un
    admin n'opère pas sur le stock.
    """
    if user.branch_id is None:
        raise NoBranchAssigned(
            "Cet utilisateur n'est rattaché à aucune succursale."
        )
    return user.branch_id


def add_stock(session, user, product_id, quantity):
    """Ajoute une quantité au stock du produit dans la succursale."""
    branch_id = _user_branch_id(user)

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise InvalidStockQuantity(
            "La quantité doit être un entier."
        )
    if quantity <= 0:
        raise InvalidStockQuantity(
            "La quantité doit être strictement positive."
        )

    stock = session.execute(
        select(Stock)
        .where(Stock.branch_id == branch_id)
        .where(Stock.product_id == product_id)
    ).scalar_one_or_none()

    if stock is not None:
        stock.quantity += quantity
    else:
        if not product_exists(product_id):
            raise ProductNotFound(
                f"Le produit {product_id} est inconnu de l'API."
            )
        stock = Stock(
            branch_id=branch_id,
            product_id=product_id,
            quantity=quantity,
        )
        session.add(stock)
    return stock


def remove_stock(session, user, product_id, quantity):
    """Retire une quantité du stock du produit dans la succursale."""
    branch_id = _user_branch_id(user)

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise InvalidStockQuantity(
            "La quantité doit être un entier."
        )
    if quantity <= 0:
        raise InvalidStockQuantity(
            "La quantité doit être strictement positive."
        )

    stock = session.execute(
        select(Stock)
        .where(Stock.branch_id == branch_id)
        .where(Stock.product_id == product_id)
    ).scalar_one_or_none()

    if stock is None or stock.quantity < quantity:
        raise InsufficientStock(
            f"Stock insuffisant pour le produit {product_id}."
        )
    stock.quantity -= quantity
    return stock


def list_stock(session, user):
    """Retourne les lignes de stock de la succursale de l'utilisateur."""
    branch_id = _user_branch_id(user)

    stocks = session.execute(
        select(Stock)
        .where(Stock.branch_id == branch_id)
        .order_by(Stock.product_id)
    ).scalars().all()
    return stocks
