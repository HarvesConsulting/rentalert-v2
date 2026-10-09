"""Ручний запуск циклу агрегації для дебагу."""

import logging
from pathlib import Path

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db.client import TursoClient
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry
from rentalert.services.aggregator import run_aggregation_cycle

# ⚡ Логування — щоб бачити INFO-логи
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)
    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

    # Обмежуємо всі Spotahome-парсери для швидкого тесту
    for key in ["spotahome", "spotahome_pt", "spotahome_de", "spotahome_fr"]:
        parser = PARSER_REGISTRY.get(key)
        if parser is not None:
            parser.MAX_PAGES = 2
    print("⚡ Spotahome (ES/PT/DE/FR): MAX_PAGES = 2")

    def notify(chat_id: str, city: str, listings: list) -> None:
        print(f"📬 {chat_id}: {city} → {len(listings)} оголошень")

    print()
    print("🚀 Запускаю цикл агрегації...")
    print()

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
