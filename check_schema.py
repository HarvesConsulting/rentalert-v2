"""Тимчасово: показати схему таблиці seen_listings."""

import os

from dotenv import load_dotenv

load_dotenv()

from rentalert.db.client import TursoClient

url = os.environ["TURSO_DATABASE_URL"]
token = os.environ["TURSO_AUTH_TOKEN"]

client = TursoClient(url, token)

rows = client.execute("PRAGMA table_info(seen_listings)")

print("=== Схема seen_listings ===")
for r in rows:
    # PRAGMA table_info повертає: cid, name, type, notnull, dflt_value, pk
    print(f"  {r[1]:25} {r[2]}")
