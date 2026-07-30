from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField,
    SelectField, IntegerField,
    )
from wtforms.validators import (
    DataRequired, InputRequired,
    Length, NumberRange
)

from models import MAX_STOCK_QUANTITY
from services.account_validation import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)


class LoginForm(FlaskForm):
    """Formulaire de connexion : identifiant et mot de passe."""
    username = StringField("Nom d'utilisateur", validators=[DataRequired()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])


class UserCreateForm(FlaskForm):
    """Formulaire de création d'un common user."""
    username = StringField(
        "Nom d'utilisateur",
        validators=[
            DataRequired(),
            Length(min=USERNAME_MIN_LENGTH, max=USERNAME_MAX_LENGTH),
        ],
    )
    password = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(),
            Length(min=PASSWORD_MIN_LENGTH, max=PASSWORD_MAX_LENGTH),
        ],
    )
    branch_id = SelectField(
        "Succursale", coerce=int, validators=[DataRequired()]
    )


class ChangePasswordForm(FlaskForm):
    """Formulaire de changement de mot de passe."""
    password = PasswordField(
        "Nouveau mot de passe",
        validators=[
            DataRequired(),
            Length(min=PASSWORD_MIN_LENGTH, max=PASSWORD_MAX_LENGTH),
        ]
    )


class ChangeBranchForm(FlaskForm):
    """Formulaire de changement de succursale."""
    branch_id = SelectField(
        "Succursale", coerce=int, validators=[DataRequired()]
    )


class StockForm(FlaskForm):
    """Opération de stock : identifiant produit et quantité."""
    product_id = IntegerField("Produit (id)", validators=[InputRequired()])
    quantity = IntegerField(
        "Quantité",
        validators=[
            InputRequired(),
            NumberRange(
                min=1,
                max=MAX_STOCK_QUANTITY,
                message=(
                    "La quantité doit être comprise entre 1 "
                    "et 1 000 000."
                ),
            ),
        ],
    )
