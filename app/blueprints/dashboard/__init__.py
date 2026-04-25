"""Dashboard blueprint."""
from flask import Blueprint

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')

from . import routes  # noqa
