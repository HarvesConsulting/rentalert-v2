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

listings = parser.fetch(kyiv, ["apartment"])
print(f"Знайдено: {len(listings)} оголошень")

# Скільки з них вже в БД?
ids = [lst.id for lst in listings]
seen = db.get_seen_ids(client, ids)
print(f"З них в БД: {len(seen)}")
print(f"Нових: {len(listings) - len(seen)}")
