"""Ручний перерахунок market_prices (Deal Score).

Використання:
    python scripts/recompute_market.py
"""

import logging
import os

from dotenv import load_dotenv

# Завантажуємо .env ДО імпорту rentalert — щоб env-змінні були доступні
load_dotenv()

from rentalert.db.client import TursoClient  # noqa: E402
from rentalert.services.market import recompute_market_prices  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    client = TursoClient(
        url=os.environ["TURSO_DATABASE_URL"],
        token=os.environ["TURSO_AUTH_TOKEN"],        # ← правильно
    )

    print("\n" + "=" * 60)
    print("Перерахунок market_prices")
    print("=" * 60 + "\n")

    count = recompute_market_prices(client, days=30, min_sample=5)
    print(f"\n✅ Оновлено груп: {count}")

    rows = client.execute(
        """
        SELECT city_slug, location_key, median_price_m2, sample_size
        FROM market_prices
        ORDER BY sample_size DESC
        LIMIT 10
        """
    )

    if not rows:
        print("\n(Поки немає даних — потрібно більше оголошень з area_m2)")
        return

    print("\nТоп-10 груп по кількості оголошень:")
    for city, key, median, n in rows:
        print(f"  {city} | {key}")
        print(f"     медіана: {float(median):.2f} / м² | {n} оголошень")


if __name__ == "__main__":
    main()
