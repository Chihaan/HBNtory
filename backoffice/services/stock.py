from sqlalchemy import select

from models import Stock
from services.errors import (
    InvalidStockQuantity,
    InsufficientStock,
    ProductNotFound,
    NoBranchAssigned
)


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
            "La quantité doit être strictement positive."
        )
    if quantity <= 0:
        raise InvalidStockQuantity(
            "La quantité doit être strictement positive."
        )


def remove_stock(session, user, product_id, quantity):
    """Retire une quantité du stock du produit dans la succursale."""
    branch_id = _user_branch_id(user)

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise InvalidStockQuantity(
            "La quantité doit être strictement positive."
        )
    if quantity <= 0:
        raise InvalidStockQuantity(
            "La quantité doit être strictement positive."
        )


def list_stock(session, user):
    """Retourne les lignes de stock de la succursale de l'utilisateur."""
    branch_id = _user_branch_id(user)
