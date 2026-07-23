from functools import wraps
from flask import abort
from flask_login import current_user

from models import UserRole


def admin_required(view):
    """Interdit la vue aux utilisateurs non-admin (403)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user.role != UserRole.ADMIN:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def common_user_required(view):
    """Interdit la vue aux utilisateurs non-common (403)."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user.role != UserRole.COMMON:
            abort(403)
        return view(*args, **kwargs)
    return wrapper
