"""Тест повного циклу з Turso: fetch_city_now + перевірка БД."""

from pathlib import Path

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db import queries as db
from rentalert.db.client import TursoClient
from rentalert.parsers.registry import build_registry
from rentalert.services.aggregator import fetch_city_now


def main() -> None:
    # 1. Перевіряємо конфіг
    if not config.TURSO_URL or not config.TURSO_TOKEN:
        print("❌ TURSO_URL або TURSO_TOKEN не задані в .env")
        return

    print(f"✅ TURSO_URL: {config.TURSO_URL[:30]}...")

    # 2. Клієнт
    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

    # 3. Каталог
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)

    # 4. Перший виклик — "перший показ"
    print("\n🔍 fetch_city_now('brno') — перший виклик...")
    listings = fetch_city_now(catalog, client, "brno")
    print(f"✅ Отримано і збережено: {len(listings)} оголошень")

    if listings:
        print("\n   Приклад:")
        first = listings[0]
        print(f"   ID:       {first.id}")
        print(f"   Title:    {first.title}")
        print(f"   Price:    {first.price}")

        # 5. Перевіряємо, що оголошення справді в БД
        ids = [lst.id for lst in listings[:5]]
        seen = db.get_seen_ids(client, ids)
        print(f"\n✅ Перевірка в БД: {len(seen)} з {len(ids)} знайдено")

    # 6. Другий виклик — має повернути 0 (бо всі вже в БД)
    print("\n🔍 fetch_city_now('brno') — другий виклик...")
    listings2 = fetch_city_now(catalog, client, "brno")
    print(f"✅ Отримано: {len(listings2)} оголошень")
    if len(listings2) == 0:
        print("   ✅ Дедуплікація працює — всі оголошення вже в БД")
    else:
        print(f"   ⚠️  Отримано {len(listings2)} — можливо, нові оголошення з'явились")


if __name__ == "__main__":
    main()
