"""Entry point: python -m rentalert."""

from __future__ import annotations

import os


def main() -> None:
    """Запускає Flask."""
    from rentalert.app import app

    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
