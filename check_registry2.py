from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

c = Catalog.load(Path("data"))
build_registry(c)

print(f"Всього парсерів: {len(PARSER_REGISTRY)}")
print(f"Ключі: {sorted(PARSER_REGISTRY.keys())}")
print(f"openrent: {PARSER_REGISTRY.get('openrent')}")
