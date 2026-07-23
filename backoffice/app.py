import os

from flask import Flask


def create_app():
    """Construit et configure l'application Flask du Backoffice."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    return app
