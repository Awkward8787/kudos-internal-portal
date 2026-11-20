import os

from flask import Flask


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(ROOT, "templates"),
        static_folder=os.path.join(ROOT, "static"),
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("KUDOS_SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.path.join(app.instance_path, "kudos.db"),
        RATE_LIMIT_PER_HOUR=10,
        DUPLICATE_WINDOW_HOURS=24,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SEED_SAMPLE_KUDOS=True,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    from . import db

    db.init_app(app)

    from . import auth, routes

    auth.init_app(app)
    app.register_blueprint(routes.bp)

    return app
