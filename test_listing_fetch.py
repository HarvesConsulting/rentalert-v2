from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

catalog = Catalog.load(Path("data"))
build_registry(catalog)

# Перевіряємо Madrid
madrid = catalog.city("madrid")
parser = PARSER_REGISTRY["habitaclia"]

print("🔎 Парсимо Madrid...")
listings = parser.fetch(madrid, ["apartment", "house", "room"])
print(f"Знайдено: {len(listings)} оголошень")
print()

# Шукаємо потрібне ID
target_id = "habitaclia:38623000004619"
found = [lst for lst in listings if lst.id == target_id]
if found:
    lst = found[0]
    print("✅ Знайдено в парсингу:")
    print(f"   ID: {lst.id}")
    print(f"   Title: {lst.title}")
    print(f"   Price: {lst.price}")
    print(f"   Location: {lst.location}")
else:
    print("❌ НЕ знайдено в парсингу Madrid")
    print()
    print("Перші 5 ID з парсингу:")
    for lst in listings[:5]:
        print(f"  {lst.id} | {lst.title[:60]}")
