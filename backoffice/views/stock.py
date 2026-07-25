from flask import (
    Blueprint, flash,
    render_template,
    redirect, url_for)

from flask_login import (
    login_required,
    current_user)

from db import SessionLocal
from models import Branch
from decorators import common_user_required
from services.stock import list_stock, add_stock, remove_stock
from forms import StockForm
from services.errors import ServiceError

stock_bp = Blueprint("stock", __name__)


@stock_bp.route("/stock")
@login_required
@common_user_required
def list_stock_view():
    """Affiche le stock de la succursale de l'utilisateur."""
    with SessionLocal() as session:
        branch = session.get(Branch, current_user.branch_id)
        stocks = list_stock(session, current_user)
        return render_template("stock/list.html",
                               stocks=stocks, branch=branch)


@stock_bp.route("/stock/add", methods=["GET", "POST"])
@login_required
@common_user_required
def add_stock_view():
    """Ajoute du stock à la succursale de l'utilisateur."""
    form = StockForm()
    with SessionLocal() as session:
        branch = session.get(Branch, current_user.branch_id)
        if form.validate_on_submit():
            try:
                add_stock(
                    session,
                    current_user,
                    form.product_id.data,
                    form.quantity.data,
                )
                session.commit()
                flash("Stock ajouté.")
                return redirect(url_for("stock.list_stock_view"))
            except ServiceError as exc:
                session.rollback()
                flash(str(exc))
        return render_template("stock/add.html", form=form, branch=branch)


@stock_bp.route("/stock/remove", methods=["GET", "POST"])
@login_required
@common_user_required
def remove_stock_view():
    """Retire du stock à la succursale de l'utilisateur."""
    form = StockForm()
    with SessionLocal() as session:
        branch = session.get(Branch, current_user.branch_id)
        if form.validate_on_submit():
            try:
                remove_stock(
                    session,
                    current_user,
                    form.product_id.data,
                    form.quantity.data,
                )
                session.commit()
                flash("Stock retiré.")
                return redirect(url_for("stock.list_stock_view"))
            except ServiceError as exc:
                session.rollback()
                flash(str(exc))
        return render_template("stock/remove.html", form=form, branch=branch)
