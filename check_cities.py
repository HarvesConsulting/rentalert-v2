from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

rows = c.execute(
    "SELECT city_slug, COUNT(*) FROM seen_listings GROUP BY city_slug ORDER BY COUNT(*) DESC"
)
print("Оголошень по містах:")
print()
for r in rows:
    print(f"  {r[0]}: {r[1]}")
