"""Flask application factory. Заглушка — заповнимо на Етапі 9."""

from flask import Flask


def create_app() -> Flask:
    """Створює і налаштовує Flask-застосунок."""
    app = Flask(__name__)
    # Flask 3.x: щоб JSON не екранував Unicode (кирилиця, емодзі)
    app.json.ensure_ascii = False  # type: ignore[attr-defined]

    @app.route("/health")
    def health() -> tuple[str, int]:
        """Health check для Render / моніторингу."""
        return "ok", 200

    return app
