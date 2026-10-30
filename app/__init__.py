import os
from pathlib import Path

import certifi
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from app.extensions import db


def _database_url(configured_url: str | None = None) -> str:
    url = configured_url if configured_url is not None else os.environ.get("DATABASE_URL")
    url = url.strip() if url and url.strip() else "sqlite:///students.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    parsed_url = make_url(url)
    if parsed_url.get_backend_name() == "postgresql":
        query = dict(parsed_url.query)
        query.update({"sslmode": "verify-full", "channel_binding": "require"})
        parsed_url = parsed_url.set(query=query)
    return parsed_url.render_as_string(hide_password=False)


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-only"),
        SQLALCHEMY_DATABASE_URI=_database_url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JSON_SORT_KEYS=False,
    )

    if test_config:
        app.config.update(test_config)

    database_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    if database_url.get_backend_name() == "sqlite":
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False}
        }
    elif database_url.get_backend_name() == "postgresql":
        engine_options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}).copy()
        connect_args = engine_options.get("connect_args", {}).copy()
        connect_args["sslrootcert"] = certifi.where()
        engine_options["connect_args"] = connect_args
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    db.init_app(app)

    from app.models import Student
    from app.routes.api import api_bp
    from app.routes.web import web_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    @app.errorhandler(404)
    def not_found(error: Exception):
        if request.path.startswith("/api/"):
            return jsonify(error="Resource not found"), 404
        return error

    @app.errorhandler(500)
    def internal_error(error: Exception):
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify(error="An unexpected server error occurred"), 500
        return error

    with app.app_context():
        db.create_all()

    return app
