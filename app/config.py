"""Configuration classes for ERP TOP."""
import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    APP_NAME = os.environ.get('APP_NAME', 'ERP TOP')
    DEFAULT_CURRENCY = os.environ.get('DEFAULT_CURRENCY', 'ر.س')
    DEFAULT_CURRENCY_CODE = os.environ.get('DEFAULT_CURRENCY_CODE', 'SAR')

    # WooCommerce
    WOO_URL = os.environ.get('WOO_URL', '')
    WOO_CONSUMER_KEY = os.environ.get('WOO_CONSUMER_KEY', '')
    WOO_CONSUMER_SECRET = os.environ.get('WOO_CONSUMER_SECRET', '')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, '..', 'instance', 'erp_top.db')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, '..', 'instance', 'erp_top.db')


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
