class ServiceError(Exception):
    """Erreur métier de la couche service.

    Distincte des erreurs de programmation : se traduit par un
    message à l'utilisateur, jamais par une 500.
    """


class InvalidStockQuantity(ServiceError):
    """La quantité demandée n'est pas un entier strictement positif."""


class InsufficientStock(ServiceError):
    """Le stock disponible ne couvre pas la quantité à retirer."""


class ProductNotFound(ServiceError):
    """L'API produits externe ne connaît pas ce product_id."""


class NoBranchAssigned(ServiceError):
    """Un utilisateur sans succursale ne peut pas opérer sur le stock."""
