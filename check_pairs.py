from pathlib import Path

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db import queries as db
from rentalert.db.client import TursoClient

catalog = Catalog.load(Path("data"))
client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

all_subs = db.get_all_user_cities(client)
print(f"Підписок: {len(all_subs)}")
print()

pairs: set[tuple[str, str]] = set()
for chat_id, cities in all_subs.items():
    print(f"chat_id {chat_id}:")
    for city_slug in cities:
        city = catalog.city(city_slug)
        if city is None:
            print(f"  ❌ {city_slug}: НЕ ЗНАЙДЕНО в каталозі")
            continue
        print(f"  ✅ {city_slug} ({city.name}): refs={list(city.refs.keys())}")
        for source_key in city.refs:
            pairs.add((city_slug, source_key))
    print()

print(f"Всього пар: {len(pairs)}")
for p in sorted(pairs):
    print(f"  {p}")
