from pathlib import Path

from rentalert.catalog.catalog import Catalog

c = Catalog.load(Path("data"))
print(f"Країн: {len(c.all_countries())}")
print(f"Джерел: {len(c.all_sources())}")
print(f"GB міст: {len(c.cities_of('gb'))}")
print(f"OpenRent source: {c.source('openrent').name if c.source('openrent') else 'НЕ ЗНАЙДЕНО'}")
