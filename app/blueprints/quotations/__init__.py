from flask import Blueprint

quotations_bp = Blueprint('quotations', __name__, url_prefix='/quotations')

from . import routes
