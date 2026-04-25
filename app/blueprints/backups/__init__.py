from flask import Blueprint

backups_bp = Blueprint('backups', __name__, url_prefix='/backups')

from . import routes
