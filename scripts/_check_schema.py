"""Тимчасова перевірка schema.py."""

from rentalert.db.schema import INDEXES, TABLES

print(f"Tables: {len(TABLES)}")
print(f"Indexes: {len(INDEXES)}")
print("OK")
