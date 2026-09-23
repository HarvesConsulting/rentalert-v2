from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

# 1. Скільки всього Barcelona?
rows = c.execute("SELECT COUNT(*) FROM seen_listings WHERE city_slug = 'barcelona'")
print(f"Barcelona всього: {rows[0][0]}")
print()

# 2. Скільки унікальних title?
rows = c.execute("SELECT COUNT(DISTINCT title) FROM seen_listings WHERE city_slug = 'barcelona'")
print(f"Унікальних title: {rows[0][0]}")
print()

# 3. Топ-10 дублікатів за title
rows = c.execute(
    "SELECT title, COUNT(*) as cnt "
    "FROM seen_listings "
    "WHERE city_slug = 'barcelona' "
    "GROUP BY title "
    "HAVING cnt > 1 "
    "ORDER BY cnt DESC "
    "LIMIT 10"
)
print("Топ-10 дублікатів за title:")
for r in rows:
    print(f"  {r[1]}x {r[0][:80]}")
print()

# 4. Скільки перших 30 (старих) і решти 417 (нових)?
rows = c.execute(
    "SELECT COUNT(*) FROM seen_listings "
    "WHERE city_slug = 'barcelona' "
    "AND first_seen < '2026-09-23 05:50:00'"
)
print(f"Старі (до 05:50): {rows[0][0]}")

rows = c.execute(
    "SELECT COUNT(*) FROM seen_listings "
    "WHERE city_slug = 'barcelona' "
    "AND first_seen >= '2026-09-23 05:50:00'"
)
print(f"Нові (після 05:50): {rows[0][0]}")
