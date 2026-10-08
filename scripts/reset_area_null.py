"""Видаляє оголошення з area_m2=NULL для повторного парсингу."""

import os

from dotenv import load_dotenv

load_dotenv()

from rentalert.db.client import TursoClient  # noqa: E402


def main() -> None:
    client = TursoClient(
        url=os.environ["TURSO_DATABASE_URL"],
        token=os.environ["TURSO_AUTH_TOKEN"],
    )

    # Скільки з NULL
    rows = client.execute(
        """
        SELECT source_key, COUNT(*)
        FROM seen_listings
        WHERE area_m2 IS NULL
        GROUP BY source_key
        ORDER BY COUNT(*) DESC
        """
    )
    print("Оголошень з area_m2=NULL:")
    for r in rows:
        print(f"  {r[0]}: {r[1]}")
    print()

    # Видалити для Pisos і Habitaclia (щоб перезаписались)
    for src in ("pisos", "habitaclia", "olx_ua", "olx_pl", "olx_pt", "olx_ro", "olx_bg"):
        affected = client.execute_non_query(
            "DELETE FROM seen_listings WHERE source_key = ? AND area_m2 IS NULL",
            [src],
        )
        print(f"Видалено {src}: {affected}")


if __name__ == "__main__":
    main()
