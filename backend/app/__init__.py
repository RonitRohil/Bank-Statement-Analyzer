import logging
from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS

from app.routes.routes import analyze_statement_bp
from app.config.config import Config

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/*": {"origins": Config.CORS_URLS}}, supports_credentials=True)

    # Register blueprints
    with app.app_context():
        app.register_blueprint(analyze_statement_bp, url_prefix="/api")

    return app
