"""REST API blueprint — JSON endpoints for all modules."""
from flask import Blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
from . import routes  # noqa
