"""Перевіряє OLX.pt: чи заповнюється area_m2."""

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
        SELECT COUNT(*) as total, COUNT(area_m2) as with_area
        FROM seen_listings
        WHERE source_key = 'olx_pt'
        """
    )
    total = int(rows[0][0]) if rows else 0
    with_area = int(rows[0][1]) if rows else 0
    pct = (100 * with_area / total) if total else 0
    print(f"olx_pt: {with_area}/{total} з площею ({pct:.0f}%)")

    # Приклади з Porto
    print("\n=== OLX.pt Porto з area_m2 (5) ===")
    rows = client.execute(
        """
        SELECT id, title, price, location, area_m2
        FROM seen_listings
        WHERE source_key = 'olx_pt' AND area_m2 IS NOT NULL
          AND location LIKE '%Porto%'
        LIMIT 5
        """
    )
    for r in rows:
        print(f"  {r[0]} | {r[1][:40]} | {r[2]} | {r[3]} | {r[4]} м²")

    # Групи market_prices для Португалії
    print("\n=== market_prices для olx_pt (топ-10) ===")
    rows = client.execute(
        """
        SELECT location_key, median_price_m2, sample_size
        FROM market_prices
        WHERE city_slug IN ('porto', 'lisboa', 'lisbon', 'maia')
        ORDER BY sample_size DESC
        LIMIT 10
        """
    )
    for r in rows:
        print(f"  {r[0]} | {r[1]:.2f} €/м² | {r[2]} оголошень")
            # Всі групи olx_pt
    print("\n=== Всі групи market_prices для olx_pt ===")
    rows = client.execute(
        """
        SELECT city_slug, location_key, median_price_m2, sample_size
        FROM market_prices
        WHERE location_key LIKE 'porto%'
           OR location_key LIKE 'lisboa%'
           OR location_key LIKE 'lisbon%'
           OR location_key LIKE 'maia%'
        ORDER BY sample_size DESC
        """
    )
    if not rows:
        print("  (порожньо)")
    for r in rows:
        print(f"  {r[0]} | {r[1]} | {r[2]:.2f} €/м² | {r[3]} оголошень")


if __name__ == "__main__":
    main()
