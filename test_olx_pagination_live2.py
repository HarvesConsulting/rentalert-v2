from pathlib import Path

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db import queries as db
from rentalert.db.client import TursoClient
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry

catalog = Catalog.load(Path("data"))
build_registry(catalog)
client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

kyiv = catalog.city("kyiv")
parser = PARSER_REGISTRY["olx_ua"]


def is_all_seen(ids: list[str]) -> bool:
    if not ids:
        return False
    seen = db.get_seen_ids(client, ids)
    return len(seen) == len(ids)


print("=== З seen_checker ===")
listings = parser.fetch(kyiv, ["apartment"], seen_checker=is_all_seen)
print(f"Знайдено: {len(listings)} оголошень")
