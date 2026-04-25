"""System Settings model."""
from ..extensions import db
from datetime import datetime

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), default='ERP TOP')
    company_logo = db.Column(db.String(300), nullable=True)
    tax_rate = db.Column(db.Float, default=15.0)
    show_tax = db.Column(db.Boolean, default=True)
    currency_symbol = db.Column(db.String(10), default='ر.س')
    exchange_rate = db.Column(db.Float, default=1.0)
    n8n_webhook_url = db.Column(db.String(500), nullable=True)
    n8n_api_key = db.Column(db.String(200), nullable=True)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_settings():
        settings = SystemSettings.query.first()
        if not settings:
            settings = SystemSettings()
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f'<SystemSettings {self.company_name}>'
