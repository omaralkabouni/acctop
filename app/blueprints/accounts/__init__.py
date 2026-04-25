"""Accounts blueprint — Chart of Accounts + Journal Entries."""
from flask import Blueprint

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')

from . import routes  # noqa
