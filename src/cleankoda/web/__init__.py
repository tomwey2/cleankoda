"""Flask application factory.

This module contains the `create_app` function that is responsible for
initializing the Flask application, configuring it, setting up extensions like
SQLAlchemy and APScheduler, and registering blueprints.
"""

import os
from pathlib import Path

from flask import Flask

from cleankoda.core.config import settings
from cleankoda.core.extensions import db
from cleankoda.core.utils import setup_logging
from cleankoda.web.routes import web_bp
from cleankoda.web.routes_credentials import credentials_bp
from cleankoda.web.routes_dashboard import dashboard_bp
from cleankoda.web.routes_settings import settings_bp


def create_app(config_class=settings) -> Flask:
    """Create and configure an instance of the Flask application."""

    # 1. Logging & Env Setup
    logger = setup_logging()
    logger.info("Initializing Web Server app...")
    config_class.log_settings()

    app = Flask(__name__, instance_relative_config=True, instance_path=config_class.instance_dir)

    # Load static config from module
    app.config.from_object("cleankoda.core.config")

    # Load dynamic config from environment settings
    app.config["SECRET_KEY"] = config_class.secret_key

    # Set database URI
    base_dir = Path(__file__).resolve().parent.parent
    app.config["SQLALCHEMY_DATABASE_URI"] = config_class.get_database_uri(base_dir)

    # Set encryption key
    app.config["ENCRYPTION_KEY"] = config_class.encryption_key

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    # scheduler.init_app(app)

    # Initialize DB tables
    with app.app_context():
        db.create_all()

    # This adds all routes from web_bp to the app
    app.register_blueprint(web_bp)
    app.register_blueprint(credentials_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    return app
