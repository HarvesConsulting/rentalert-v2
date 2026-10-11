"""Ручний запуск циклу агрегації для дебагу.

Використовується і локально, і на GitHub Actions.
"""

import logging
import sys
from pathlib import Path

# Додаємо scripts/ до sys.path, щоб імпортувати notify_standalone
sys.path.insert(0, str(Path(__file__).parent))

from notify_standalone import make_notify_fn

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db.client import TursoClient
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry
from rentalert.services.aggregator import run_aggregation_cycle
from rentalert.services.notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)
    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

    # Обмежуємо Spotahome для швидкого тесту
    for key in ["spotahome", "spotahome_pt", "spotahome_de", "spotahome_fr"]:
        parser = PARSER_REGISTRY.get(key)
        if parser is not None:
            parser.MAX_PAGES = 2
    print("⚡ Spotahome (ES/PT/DE/FR): MAX_PAGES = 2")

    # Створюємо справжній notifier
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN)
    notify_fn = make_notify_fn(client, catalog, notifier)

    print()
    print("🚀 Запускаю цикл агрегації...")
    print()

    stats = run_aggregation_cycle(
        catalog,
        client,
        notify_fn,
        recent_hours=24,
    )

    print()
    print(f"📊 Статистика: {stats}")


if __name__ == "__main__":
    main()
