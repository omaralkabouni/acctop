"""Auth blueprint — login, logout, register, user management."""
from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

from . import routes  # noqa
