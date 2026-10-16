"""Видаляє оголошення оренди старіші за N днів з Turso (RentAlert)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rentalert import config
from rentalert.db.client import TursoClient

DAYS_OLD = 7


def main() -> None:
    print(f"=== Cleanup RentAlert: видаляю старіші за {DAYS_OLD} днів ===")

    if not config.TURSO_URL or not config.TURSO_TOKEN:
        print("❌ TURSO_URL або TURSO_TOKEN не задано")
        return

    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

    # Скільки до
    rows = client.execute("SELECT COUNT(*) FROM seen_listings")
    before = int(rows[0][0]) if rows else 0
    print(f"Listings до: {before}")

    # Скільки старих
    rows = client.execute(
        "SELECT COUNT(*) FROM seen_listings WHERE first_seen < datetime('now', ?)",
        [f"-{DAYS_OLD} days"],
    )
    old_count = int(rows[0][0]) if rows else 0
    print(f"Старіших за {DAYS_OLD} днів: {old_count}")

    if old_count == 0:
        print("Нічого видаляти.")
        return

    # Видалити
    client.execute_non_query(
        "DELETE FROM seen_listings WHERE first_seen < datetime('now', ?)",
        [f"-{DAYS_OLD} days"],
    )

    # Скільки після
    rows = client.execute("SELECT COUNT(*) FROM seen_listings")
    after = int(rows[0][0]) if rows else 0
    print(f"Listings після: {after}")
    print(f"✅ Видалено: {before - after}")


if __name__ == "__main__":
    main()
