from flask import Blueprint

vouchers_bp = Blueprint('vouchers', __name__, url_prefix='/vouchers')

from . import routes
