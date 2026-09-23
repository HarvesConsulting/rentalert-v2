from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

catalog = Catalog.load(Path("data"))
build_registry(catalog)

kyiv = catalog.city("kyiv")
parser = PARSER_REGISTRY["olx_ua"]

print("=== БЕЗ seen_checker ===")
listings = parser.fetch(kyiv, ["apartment"])
print(f"Знайдено: {len(listings)} оголошень")
