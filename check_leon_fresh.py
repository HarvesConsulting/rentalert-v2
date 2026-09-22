from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

# Останні 10 Leon
rows = c.execute(
    "SELECT id, title, first_seen "
    "FROM seen_listings "
    "WHERE city_slug = 'leon-40150' "
    "ORDER BY first_seen DESC "
    "LIMIT 10"
)
print("Останні 10 Leon:")
for r in rows:
    print(f"  {r[2]} | {r[1][:50]}")
