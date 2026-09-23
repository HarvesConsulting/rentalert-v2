from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

# 1. Скільки Barcelona за різними first_seen
rows = c.execute(
    "SELECT DATE(first_seen) as day, COUNT(*) "
    "FROM seen_listings "
    "WHERE city_slug = 'barcelona' "
    "GROUP BY day "
    "ORDER BY day"
)
print("Barcelona по днях:")
for r in rows:
    print(f"  {r[0]}: {r[1]}")
print()

# 2. Скільки за останні 24 год, розбито по годинах
rows = c.execute(
    "SELECT strftime('%Y-%m-%d %H:00', first_seen) as hour, COUNT(*) "
    "FROM seen_listings "
    "WHERE city_slug = 'barcelona' "
    "AND first_seen >= '2026-09-22 00:00:00' "
    "GROUP BY hour "
    "ORDER BY hour"
)
print("Barcelona по годинах (з 22.09):")
for r in rows:
    print(f"  {r[0]}: {r[1]}")
