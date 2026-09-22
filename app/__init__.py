"""Flask application factory (FNA-6)."""

import os

from dotenv import load_dotenv
from flask import Flask


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config["LLM_PROVIDER"] = os.getenv("LLM_PROVIDER", "demo")
    app.config["PIPELINE_VERSION"] = os.getenv("PIPELINE_VERSION", "v1")

    from .routes import bp

    app.register_blueprint(bp)
    return app
