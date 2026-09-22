"""Тест пагінації Habitaclia з seen_checker."""

from pathlib import Path

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db import queries as db
from rentalert.db.client import TursoClient
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

catalog = Catalog.load(Path("data"))
build_registry(catalog)
client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

barcelona = catalog.city("barcelona")
if barcelona is None:
    print("❌ Barcelona не знайдено")
    exit(1)

parser = PARSER_REGISTRY["habitaclia"]
print(f"Парсер: {parser}")
print()

# ─────────────────────────────────────────────────
# Тест 1: БЕЗ seen_checker — тягне всі сторінки
# ─────────────────────────────────────────────────
print("=== Тест 1: БЕЗ seen_checker (всі сторінки) ===")
listings_no_check = parser.fetch(barcelona, ["apartment", "house", "room"])
print(f"✅ Знайдено: {len(listings_no_check)} оголошень")
print()

# ─────────────────────────────────────────────────
# Тест 2: З seen_checker — зупиняється, коли всі в БД
# ─────────────────────────────────────────────────
print("=== Тест 2: З seen_checker (зупинка, коли всі в БД) ===")


def is_all_seen(ids: list[str]) -> bool:
    if not ids:
        return False
    seen = db.get_seen_ids(client, ids)
    return len(seen) == len(ids)


listings_with_check = parser.fetch(
    barcelona,
    ["apartment", "house", "room"],
    seen_checker=is_all_seen,
)
print(f"✅ Знайдено: {len(listings_with_check)} оголошень")
print()

# ─────────────────────────────────────────────────
# Порівняння
# ─────────────────────────────────────────────────
print("=== Підсумок ===")
print(f"Без seen_checker: {len(listings_no_check)} оголошень")
print(f"З seen_checker:   {len(listings_with_check)} оголошень")
print()

if len(listings_with_check) < len(listings_no_check):
    print("✅ Пагінація працює — з seen_checker зупинилась раніше")
elif len(listings_with_check) == len(listings_no_check):
    print("⚠️ Однакова кількість — можливо, всі оголошення нові (перший запуск)")
else:
    print("❌ Помилка — з seen_checker більше, ніж без")
