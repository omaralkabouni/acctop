"""
ERP TOP Application Factory
"""
from flask import Flask
from .config import config_by_name
from .extensions import db, login_manager, csrf, migrate


def create_app(config_name='development'):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_by_name[config_name])

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.dashboard import dashboard_bp
    from .blueprints.accounts import accounts_bp
    from .blueprints.invoices import invoices_bp
    from .blueprints.expenses import expenses_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.parties import parties_bp
    from .blueprints.reports import reports_bp
    from .blueprints.woocommerce import woo_bp
    from .blueprints.api import api_bp
    from .blueprints.vouchers import vouchers_bp
    from .blueprints.settings import settings_bp
    from .blueprints.purchases import purchases_bp
    from .blueprints.backups import backups_bp
    from .blueprints.quotations import quotations_bp
    from .blueprints.pos import pos_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(parties_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(woo_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(vouchers_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(backups_bp)
    app.register_blueprint(quotations_bp)
    app.register_blueprint(pos_bp)

    # Template filters
    from .utils.helpers import format_currency, format_date, arabic_number, rzero
    app.jinja_env.filters['currency'] = format_currency
    app.jinja_env.filters['fdate'] = format_date
    app.jinja_env.filters['arnum'] = arabic_number
    app.jinja_env.filters['rzero'] = rzero

    # Global template variables
    from datetime import date
    from .models.settings import SystemSettings
    @app.context_processor
    def inject_globals():
        # Using a getter to avoid DB issues during startup/migration
        try:
            sys_settings = SystemSettings.query.first()
        except:
            sys_settings = None
        return dict(
            today=date.today().isoformat(), 
            current_date=date.today(),
            sys_settings=sys_settings
        )

    # Automatic DB update
    with app.app_context():
        db.create_all()

    return app
