import sys

from rentalert import config
from rentalert.db.client import TursoClient

# ID з посилання
listing_id = sys.argv[1] if len(sys.argv) > 1 else "habitaclia:38623000004619"

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

rows = c.execute(
    "SELECT id, title, price, location, city_slug, first_seen FROM seen_listings WHERE id = ?",
    [listing_id],
)
if rows:
    r = rows[0]
    print("✅ Знайдено в БД:")
    print(f"   ID: {r[0]}")
    print(f"   Title: {r[1]}")
    print(f"   Price: {r[2]}")
    print(f"   Location: {r[3]}")
    print(f"   City: {r[4]}")
    print(f"   First seen: {r[5]}")
else:
    print(f"❌ НЕ знайдено в БД: {listing_id}")
