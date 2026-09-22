"""Тест парсера OpenRent на реальному місті."""

from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

# Завантажуємо каталог
catalog = Catalog.load(Path("data"))
build_registry(catalog)

# Беремо London
london = catalog.city("london")
if london is None:
    print("❌ London не знайдено в каталозі")
    print("Доступні міста (перші 5):")
    for c in catalog.cities_of("gb")[:5]:
        print(f"  {c.slug} → {c.name}")
    exit(1)

print(f"📍 Місто: {london.name}")
print(f"   slug: {london.slug}")
print(f"   refs: {london.refs}")
print()

# Отримуємо парсер
parser = PARSER_REGISTRY.get("openrent")
if parser is None:
    print("❌ Парсер openrent не знайдено")
    exit(1)

print(f"🔧 Парсер: {parser}")
print()

# Парсимо
print("🔎 Парсимо оголошення...")
listings = parser.fetch(london, ["apartment", "house", "room"])

print(f"✅ Знайдено: {len(listings)} оголошень")
print()

# Показуємо перші 5
for i, lst in enumerate(listings[:5], 1):
    print(f"  {i}. {lst.price}")
    print(f"     {lst.title[:80]}")
    print(f"     📍 {lst.location}")
    print(f"     🛏 {lst.rooms} кімн.")
    print(f"     📷 {lst.photo[:60] if lst.photo else '—'}")
    print(f"     🔗 {lst.link}")
    print()
