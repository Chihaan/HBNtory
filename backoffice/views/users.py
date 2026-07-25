from flask import (
    Blueprint, render_template,
    redirect, flash, url_for
)
from flask_login import login_required
from sqlalchemy import select

from db import SessionLocal
from decorators import admin_required
from services.users import (
    list_users, create_user,
    soft_delete_user,
    change_password,
    change_branch
)
from forms import (
    UserCreateForm, ChangePasswordForm,
    ChangeBranchForm
)
from models import Branch
from services.errors import (
    UsernameAlreadyUsed,
    ServiceError
)

users_bp = Blueprint("users", __name__)


@users_bp.route("/users")
@login_required
@admin_required
def list_users_view():
    """Affiche la liste des utilisateurs et les KPIs (admin)."""
    with SessionLocal() as session:
        users = list_users(session)
        deleted = sum(1 for u in users if u.deleted_at is not None)
        inactive = sum(
            1 for u in users
            if u.deleted_at is None and not u.is_active
        )
        active = sum(
            1 for u in users
            if u.deleted_at is None and u.is_active
        )
        kpis = {
            "total": active + inactive,
            "active": active,
            "inactive": inactive,
            "deleted": deleted,
        }
        return render_template("users/list.html",
                               users=users, kpis=kpis)


@users_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_user_view():
    """Crée un common user (admin uniquement)."""
    form = UserCreateForm()
    with SessionLocal() as session:
        branches = session.execute(
            select(Branch)
            .order_by(Branch.name)
        ).scalars().all()
        form.branch_id.choices = [(b.id, b.name) for b in branches]
        if form.validate_on_submit():
            try:
                create_user(
                    session,
                    form.username.data,
                    form.password.data,
                    form.branch_id.data,
                )
                session.commit()
                flash("Utilisateur créé.", "success")
                return redirect(url_for("users.list_users_view"))
            except UsernameAlreadyUsed as exc:
                session.rollback()
                flash(str(exc), "error")
        return render_template("users/new.html", form=form)


@users_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user_view(user_id):
    """Soft-delete un utilisateur (admin uniquement)."""
    with SessionLocal() as session:
        try:
            soft_delete_user(session, user_id)
            session.commit()
            flash("Utilisateur supprimé.", "success")
        except ServiceError as exc:
            session.rollback()
            flash(str(exc), "error")
        return redirect(url_for("users.list_users_view"))


@users_bp.route("/users/<int:user_id>/password", methods=["GET", "POST"])
@login_required
@admin_required
def change_user_password_view(user_id):
    """Change le mot de passe d'un utilisateur (admin uniquement)."""
    form = ChangePasswordForm()
    with SessionLocal() as session:
        if form.validate_on_submit():
            try:
                change_password(session, user_id, form.password.data)
                session.commit()
                flash("Mot de passe modifié.", "success")
                return redirect(url_for("users.list_users_view"))
            except ServiceError as exc:
                session.rollback()
                flash(str(exc), "error")
    return render_template("users/password.html", form=form)


@users_bp.route("/users/<int:user_id>/branch", methods=["GET", "POST"])
@login_required
@admin_required
def change_user_branch_view(user_id):
    """Change la succursale d'un utilisateur (admin uniquement)."""
    form = ChangeBranchForm()
    with SessionLocal() as session:
        branches = session.execute(
            select(Branch)
            .order_by(Branch.name)
        ).scalars().all()

        form.branch_id.choices = [(b.id, b.name) for b in branches]

        if form.validate_on_submit():
            try:
                change_branch(session, user_id, form.branch_id.data)
                session.commit()
                flash("Succursale modifiée.", "success")
                return redirect(url_for("users.list_users_view"))
            except ServiceError as exc:
                session.rollback()
                flash(str(exc), "error")

        return render_template("users/branch.html", form=form)
