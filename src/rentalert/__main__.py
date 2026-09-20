"""Entry point: python -m renalert."""

import os


def main() -> None:
    """Запускає Flask-застосунок."""
    from rentalert.app import create_app  # noqa: PLC0415

    port = int(os.environ.get("PORT", "3000"))
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()