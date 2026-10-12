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

    # Якщо задано CITY_SLUG (через workflow_dispatch) — парсимо тільки його
    import os

    only_city_slug = os.environ.get("CITY_SLUG") or None
    if only_city_slug:
        print(f"🎯 Запуск для одного міста: {only_city_slug}")

    stats = run_aggregation_cycle(
        catalog,
        client,
        notify_fn,
        recent_hours=24,
        only_city_slug=only_city_slug,
    )

    print()
    print(f"📊 Статистика: {stats}")

    # ── Перший показ: 5 з кожного джерела ──
    first_show_chat_id = os.environ.get("CHAT_ID") or None
    if first_show_chat_id and only_city_slug:
        print(f"🎁 Перший показ для {first_show_chat_id}: {only_city_slug}")
        try:
            from notify_standalone import send_first_show

            send_first_show(
                client,
                catalog,
                notifier,
                first_show_chat_id,
                only_city_slug,
            )
            print("✅ Перший показ надіслано")
        except Exception as e:
            print(f"❌ Помилка першого показу: {e}")


if __name__ == "__main__":
    main()
