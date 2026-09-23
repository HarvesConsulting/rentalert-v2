from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

rows = c.execute(
    "SELECT id, title, price, location, link "
    "FROM seen_listings "
    "WHERE city_slug = 'barcelona' "
    "AND title = 'Piso con terraza en alquiler en Ciutat Vella' "
    "LIMIT 5"
)
print(f"Знайдено: {len(rows)}")
for r in rows:
    print(f"  ID: {r[0]}")
    print(f"  Title: {r[1]}")
    print(f"  Price: {r[2]}")
    print(f"  Location: {r[3]}")
    print(f"  Link: {r[4][:80]}")
    print()
