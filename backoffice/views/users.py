from flask import Blueprint, render_template
from flask_login import login_required

from db import SessionLocal
from decorators import admin_required
from services.users import list_users

users_bp = Blueprint("users", __name__)


@users_bp.route("/users")
@login_required
@admin_required
def list_users_view():
    """Affiche la liste des utilisateurs (admin uniquement)."""
    with SessionLocal() as session:
        users = list_users(session)
        return render_template("users/list.html", users=users)
