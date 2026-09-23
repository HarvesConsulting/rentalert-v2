from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

catalog = Catalog.load(Path("data"))
build_registry(catalog)

paris = catalog.city("paris-75056")
parser = PARSER_REGISTRY["bienici"]

listings = parser.fetch(paris, ["apartment", "house"])
print(f"Знайдено: {len(listings)} оголошень")
