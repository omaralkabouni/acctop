"""WooCommerce integration blueprint."""
from flask import Blueprint
woo_bp = Blueprint('woocommerce', __name__, url_prefix='/woocommerce')
from . import routes  # noqa
