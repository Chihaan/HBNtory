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
    app.config["ASSISTANT_URL"] = os.environ.get(
        "ASSISTANT_URL", "http://localhost:8080"
    )
    # Durcissement du cookie de session.
    # HttpOnly (défaut) + SameSite=Lax bloquent le vol via JS et limitent
    # le CSRF. Secure=True (cookie uniquement en HTTPS) à activer en prod
    # via l'env ; désactivé par défaut pour le dev/tests en HTTP.
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(stock_bp)

    app.context_processor(profile_context)
    return app


def profile_context():
    """Injecte le libellé de rôle et le nom de succursale au profil."""
    from flask_login import current_user
    from models import Branch, UserRole

    labels = {UserRole.ADMIN: "Administrateur", UserRole.COMMON: "Employé"}
    role_label = None
    branch_name = None
    if current_user.is_authenticated:
        role_label = labels.get(current_user.role)
        if current_user.branch_id is not None:
            with SessionLocal() as session:
                branch = session.get(Branch, current_user.branch_id)
                branch_name = branch.name if branch else None
    return {"role_label": role_label, "branch_name": branch_name}


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
