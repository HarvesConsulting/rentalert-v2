"""Перевіряє, що Deal Score формується для реальних оголошень."""

import os

from dotenv import load_dotenv

load_dotenv()

from rentalert.db.client import TursoClient  # noqa: E402
from rentalert.services.market import get_deal_score  # noqa: E402


def main() -> None:
    client = TursoClient(
        url=os.environ["TURSO_DATABASE_URL"],
        token=os.environ["TURSO_AUTH_TOKEN"],
    )

    rows = client.execute(
        """
        SELECT id, title, price, location, category, rooms, area_m2, city_slug
        FROM seen_listings
        WHERE source_key = '999md' AND area_m2 IS NOT NULL
        LIMIT 10
        """
    )

    print(f"{'title':<45} | {'price':<10} | {'area':>6} | score")
    print("-" * 110)

    with_score = 0
    for _, title, price, location, category, rooms, area_m2, city_slug in rows:
        score = get_deal_score(
            client,
            city_slug=str(city_slug),
            location=location,
            category=category,
            rooms=rooms,
            price_str=price,
            area_m2=float(area_m2) if area_m2 else None,
        )
        score_str = f"{score.emoji} {score.label}" if score else "—"
        if score:
            with_score += 1
        print(f"{str(title)[:44]:<45} | {price!s:<10} | {area_m2:>6} | {score_str}")

    print(f"\n✅ З Deal Score: {with_score}/{len(rows)}")


if __name__ == "__main__":
    main()
