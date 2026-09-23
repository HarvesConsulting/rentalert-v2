from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

rows = c.execute(
    "SELECT COUNT(*) FROM seen_listings WHERE source_key = 'olx_ua' AND city_slug = 'kyiv'"
)
print(f"OLX Київ в БД: {rows[0][0]}")
