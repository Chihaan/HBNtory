from flask import (
    Blueprint, flash,
    redirect, url_for,
    render_template)
from flask_login import login_user
from sqlalchemy import select

from forms import LoginForm
from db import SessionLocal
from models import User
from services.auth import check_password

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
                flash("Identifiant ou mot de passe incorrect.")
                return redirect(url_for("auth.login"))

            if not check_password(user, form.password.data):
                flash("Identifiant ou mot de passe incorrect.")
                return redirect(url_for("auth.login"))
            login_user(user)
            return redirect(url_for("dashboard"))
    return render_template("login.html", form=form)
