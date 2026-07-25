from flask import (
    Blueprint, flash,
    redirect, url_for,
    render_template)

from flask_login import (
    login_user,
    login_required,
    logout_user,
    current_user)

from sqlalchemy import select

from forms import LoginForm
from db import SessionLocal
from models import User, UserRole
from services.auth import check_password, waste_time

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Affiche le formulaire de login et traite la connexion."""
    form = LoginForm()
    if form.validate_on_submit():
        with SessionLocal() as session:
            user = session.execute(
                select(User)
                .where(User.username == form.username.data)
            ).scalar_one_or_none()

            invalid = (
                user is None
                or user.deleted_at is not None
                or not user.is_active
            )

            if invalid:
                waste_time()
                flash("Identifiant ou mot de passe incorrect.", "error")
                return redirect(url_for("auth.login"))

            if not check_password(user, form.password.data):
                flash("Identifiant ou mot de passe incorrect.", "error")
                return redirect(url_for("auth.login"))

            login_user(user)
            return redirect(url_for("auth.dashboard"))

    return render_template("login.html", form=form)


@auth_bp.route("/")
@login_required
def dashboard():
    """Redirige chaque rôle vers sa page principale."""
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for("users.list_users_view"))
    return redirect(url_for("stock.list_stock_view"))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Déconnecte l'utilisateur et vide sa session."""
    logout_user()
    return redirect(url_for("auth.login"))
