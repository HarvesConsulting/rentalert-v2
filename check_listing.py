"""Тимчасово: перевірити, чи є оголошення в БД."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from rentalert.db.client import TursoClient

LISTING_ID = sys.argv[1] if len(sys.argv) > 1 else "olx_pt:IDJBuoA"

url = os.environ["TURSO_DATABASE_URL"]
token = os.environ["TURSO_AUTH_TOKEN"]

client = TursoClient(url, token)

# 1. Перевіряємо конкретне оголошення
rows = client.execute(
    """
    SELECT id, source_key, city_slug, title, price, location,
           link, rooms, category, created_at, first_seen
    FROM seen_listings
    WHERE id = ?
    """,
    [LISTING_ID],
)

print(f"=== Перевірка: {LISTING_ID} ===")
if not rows:
    print("❌ NOT FOUND")
else:
    r = rows[0]
    print("✅ FOUND")
    print(f"   source_key:  {r[1]}")
    print(f"   city_slug:   {r[2]}")
    print(f"   title:       {r[3]}")
    print(f"   price:       {r[4]}")
    print(f"   location:    {r[5]}")
    print(f"   link:        {r[6]}")
    print(f"   rooms:       {r[7]}")
    print(f"   category:    {r[8]}")
    print(f"   created_at:  {r[9]}")
    print(f"   first_seen:  {r[10]}")

print()

# 2. Розподіл по source_key
print("=== Розподіл по джерелах ===")
rows = client.execute(
    """
    SELECT source_key, COUNT(*) as cnt
    FROM seen_listings
    GROUP BY source_key
    ORDER BY cnt DESC
    """
)
for r in rows:
    print(f"   {r[0]:20} {r[1]}")

print()

# 3. Всього оголошень
rows = client.execute("SELECT COUNT(*) FROM seen_listings")
print(f"=== Всього: {rows[0][0]} ===")

# 4. olx_pt окремо
rows = client.execute("SELECT COUNT(*) FROM seen_listings WHERE source_key = 'olx_pt'")
print(f"=== olx_pt: {rows[0][0]} ===")

# 5. Топ-5 olx_pt (для перевірки ID)
print()
print("=== Топ-5 olx_pt за created_at ===")
rows = client.execute(
    """
    SELECT id, city_slug, title, created_at
    FROM seen_listings
    WHERE source_key = 'olx_pt'
    ORDER BY created_at DESC
    LIMIT 5
    """
)
for r in rows:
    print(f"   {r[0]}")
    print(f"      city: {r[1]}")
    print(f"      title: {(r[2] or '')[:60]}")
    print(f"      created: {r[3]}")
    print()
