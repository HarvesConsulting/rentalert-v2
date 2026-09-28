"""Встановлює priority=True тільки для топ-10 чеських міст."""

import json
from pathlib import Path

PRIORITY_CITIES = {
    "Praha",
    "Brno",
    "Ostrava",
    "Plzeň",
    "Liberec",
    "Olomouc",
    "České Budějovice",
    "Hradec Králové",
    "Pardubice",
    "Ústí nad Labem",
}

CZ_PATH = Path("data/cities/cz.json")
data = json.loads(CZ_PATH.read_text(encoding="utf-8"))

priority_count = 0
for city in data["cities"]:
    if city["name"] in PRIORITY_CITIES:
        city["priority"] = True
        priority_count += 1
    else:
        city["priority"] = False

CZ_PATH.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"✅ Пріоритетних: {priority_count}")
print(f"   Решта: {len(data['cities']) - priority_count}")
print()
print("Пріоритетні міста:")
for city in data["cities"]:
    if city["priority"]:
        print(f"  • {city['name']}")
