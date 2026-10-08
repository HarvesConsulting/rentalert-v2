"""Перевіряє, чи Pisos/Habitaclia заповнюють area_m2."""

import os

from dotenv import load_dotenv

load_dotenv()

from rentalert.db.client import TursoClient  # noqa: E402


def main() -> None:
    client = TursoClient(
        url=os.environ["TURSO_DATABASE_URL"],
        token=os.environ["TURSO_AUTH_TOKEN"],
    )

    rows = client.execute(
        """
        SELECT source_key, COUNT(*) as total, COUNT(area_m2) as with_area
        FROM seen_listings
        WHERE source_key IN ('pisos', 'habitaclia')
        GROUP BY source_key
        """
    )

    print("=== Pisos / Habitaclia ===")
    for source_key, total, with_area in rows:
        # Явно конвертуємо в int
        total_int = int(total) if total is not None else 0
        with_area_int = int(with_area) if with_area is not None else 0
        pct = (100 * with_area_int / total_int) if total_int else 0
        print(f"  {source_key}: {with_area_int}/{total_int} з площею ({pct:.0f}%)")

    # Приклади без area
    print("\n=== Приклади Pisos без area_m2 (5) ===")
    rows = client.execute(
        """
        SELECT id, title, price, area_m2
        FROM seen_listings
        WHERE source_key = 'pisos' AND area_m2 IS NULL
        LIMIT 5
        """
    )
    for r in rows:
        title = (r[1] or "")[:50]
        print(f"  {r[0]} | {title} | {r[2]}")

    # Приклади з area
    print("\n=== Приклади Pisos з area_m2 (5) ===")
    rows = client.execute(
        """
        SELECT id, title, price, area_m2
        FROM seen_listings
        WHERE source_key = 'pisos' AND area_m2 IS NOT NULL
        LIMIT 5
        """
    )
    for r in rows:
        title = (r[1] or "")[:50]
        print(f"  {r[0]} | {title} | {r[2]} | {r[3]} м²")


if __name__ == "__main__":
    main()
