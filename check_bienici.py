from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

# 1. Всі Bien'ici оголошення
rows = c.execute(
    "SELECT id, title, city_slug, first_seen "
    "FROM seen_listings "
    "WHERE source_key = 'bienici' "
    "ORDER BY first_seen DESC "
    "LIMIT 10"
)
print(f"Bien'ici оголошень (останні 10): {len(rows)}")
print()
for r in rows:
    print(f"  {r[0][:50]}")
    print(f"    city: {r[2]} | first_seen: {r[3]}")
print()

# 2. Загальна кількість
rows = c.execute("SELECT COUNT(*) FROM seen_listings WHERE source_key = 'bienici'")
total = rows[0][0] if rows else 0
print(f"Всього Bien'ici оголошень: {total}")
