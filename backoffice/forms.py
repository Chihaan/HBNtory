from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from wtforms.validators import DataRequired


class LoginForm(FlaskForm):
    """Formulaire de connexion : identifiant et mot de passe."""
    username = StringField("Nom d'utilisateur", validators=[DataRequired()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])


class UserCreateForm(FlaskForm):
    """Formulaire de création d'un common user."""
    username = StringField("Nom d'utilisateur", validators=[DataRequired()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])
    branch_id = SelectField(
        "Succursale", coerce=int, validators=[DataRequired()]
    )


class ChangePasswordForm(FlaskForm):
    """Formulaire de changement de mot de passe."""
    password = PasswordField("Nouveau mot de passe",
                             validators=[DataRequired()])
