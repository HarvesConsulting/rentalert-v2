"""Ручний запуск циклу агрегації для дебагу."""

from pathlib import Path

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db.client import TursoClient
from rentalert.parsers.registry import build_registry
from rentalert.services.aggregator import run_aggregation_cycle


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)
    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

    def notify(chat_id: str, city: str, listings: list) -> None:
        print(f"📬 {chat_id}: {city} → {len(listings)} оголошень")

    stats = run_aggregation_cycle(
        catalog,
        client,
        notify,
        recent_hours=24,
    )

    print()
    print(f"📊 Статистика: {stats}")


if __name__ == "__main__":
    main()
