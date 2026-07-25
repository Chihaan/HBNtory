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
from services.products import list_products
from forms import StockForm
from services.errors import ServiceError, ProductApiUnavailable

stock_bp = Blueprint("stock", __name__)


@stock_bp.route("/stock")
@login_required
@common_user_required
def list_stock_view():
    """Affiche le stock enrichi (nom/prix API) de la succursale."""
    with SessionLocal() as session:
        branch = session.get(Branch, current_user.branch_id)
        stocks = list_stock(session, current_user)

    try:
        products = {p["id"]: p for p in list_products()}
        api_ok = True
    except ProductApiUnavailable:
        products = {}
        api_ok = False

    rows = []
    total_value = 0.0
    out_of_stock = 0
    for line in stocks:
        product = products.get(line.product_id)
        price = product["unit_price"] if product else None
        if price is not None:
            total_value += price * line.quantity
        if line.quantity == 0:
            out_of_stock += 1
        rows.append({
            "product_id": line.product_id,
            "quantity": line.quantity,
            "name": product["name"] if product else None,
            "price": price,
            "description": product["description"] if product else None,
        })

    kpis = {
        "count": len(rows),
        "total_value": total_value if api_ok else None,
        "out_of_stock": out_of_stock,
    }
    return render_template("stock/list.html", branch=branch,
                           rows=rows, kpis=kpis, api_ok=api_ok)


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
                flash("Stock ajouté.", "success")
                return redirect(url_for("stock.list_stock_view"))
            except ServiceError as exc:
                session.rollback()
                flash(str(exc), "error")
    try:
        products = list_products()
    except ProductApiUnavailable:
        products = []
    return render_template("stock/add.html", form=form,
                           branch=branch, products=products)


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
                flash("Stock retiré.", "success")
                return redirect(url_for("stock.list_stock_view"))
            except ServiceError as exc:
                session.rollback()
                flash(str(exc), "error")
    try:
        products = list_products()
    except ProductApiUnavailable:
        products = []
    return render_template("stock/remove.html", form=form,
                           branch=branch, products=products)
