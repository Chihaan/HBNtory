import os

from flask import Flask
from flask_wtf import CSRFProtect
from flask_login import LoginManager
from sqlalchemy import select

from db import SessionLocal
from models import User

from views.auth import auth_bp
from views.users import users_bp
from views.stock import stock_bp

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    """Construit et configure l'application Flask du Backoffice."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    from views.auth import auth_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(stock_bp)
    return app


@login_manager.user_loader
def user_loader(user_id: str) -> User | None:
    """Recharge l'utilisateur d'une session à chaque requête.

    Appelée par Flask-Login avec l'id stocké dans le cookie signé.
    Retourne None si l'utilisateur est introuvable ou soft-deleted,
    ce qui invalide immédiatement sa session.
    """
    with SessionLocal() as session:
        user = session.execute(
            select(User)
            .where(User.id == int(user_id))
            .where(User.deleted_at.is_(None))
            .where(User.is_active.is_(True))
        ).scalar_one_or_none()
    return user
