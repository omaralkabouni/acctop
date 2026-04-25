"""Parties blueprint — customers and suppliers."""
from flask import Blueprint
parties_bp = Blueprint('parties', __name__, url_prefix='/parties')
from . import routes  # noqa
