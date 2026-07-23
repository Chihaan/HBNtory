from flask import Blueprint

from forms import LoginForm
from services.auth import check_password

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Affiche le formulaire de login et traite la connexion."""
    form = LoginForm()
    return "TODO"
