"""Тимчасово: перевірити KleinanzeigenParser."""

from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

catalog = Catalog.load(Path("data"))
build_registry(catalog)

parser = PARSER_REGISTRY.get("kleinanzeigen")
if not parser:
    print("❌ Парсер не знайдено")
    raise SystemExit(1)

city = catalog.city("berlin")
if not city:
    print("❌ Berlin не знайдено в каталозі")
    raise SystemExit(1)

print(f"City: {city.slug} ({city.name})")
print(f"Refs: {city.refs}")
print()

# Перевірка, чи є olx_pt у source config
print(f"Source: {parser.source.key}")
print(f"Config: {parser.source.config}")
print()

# Спроба fetch
try:
    listings = parser.fetch(city, ["apartment", "house", "room"])
    print(f"✅ Знайдено: {len(listings)} оголошень")
    for lst in listings[:5]:
        print(f"  {lst.id} | {lst.title[:60]} | {lst.price} | {lst.city_slug}")
except Exception as e:
    import traceback

    traceback.print_exc()
