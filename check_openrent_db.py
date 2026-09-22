from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

rows = c.execute(
    "SELECT id, title, city_slug, first_seen "
    "FROM seen_listings "
    "WHERE source_key = 'openrent' "
    "ORDER BY first_seen DESC "
    "LIMIT 10"
)
print(f"OpenRent оголошень: {len(rows)}")
print()
for r in rows:
    print(f"  {r[2]} | {r[1][:60]}")
    print(f"    first_seen: {r[3]}")
