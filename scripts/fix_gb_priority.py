"""Встановлює priority=True для найбільших британських регіонів.

OpenRent використовує графства (не міста):
- Kent, Essex, Surrey, Hampshire — великі графства
- London — єдине місто в списку
"""

import json
from pathlib import Path

# Тільки ті, що РЕАЛЬНО Є в gb.json
PRIORITY_REGIONS = {
    "london",
    "kent",
    "essex",
    "surrey",
    "hampshire",
    "lancashire",
    "devon",
    "cornwall",
    "cheshire",
    "derbyshire",
    "norfolk",
    "suffolk",
    "nottinghamshire",
    "leicestershire",
    "staffordshire",
    "worcestershire",
    "warwickshire",
    "oxfordshire",
    "cambridgeshire",
    "norfolk",
    "hertfordshire",
    "bedfordshire",
    "berkshire",
    "buckinghamshire",
    "dorset",
    "somerset",
    "wiltshire",
    "gloucestershire",
    "herefordshire",
    "shropshire",
    "northamptonshire",
    "northumberland",
    "durham",
    "cumbria",
    "north-yorkshire",
    "west-sussex",
    "east-sussex",
    "somerset",
    "sussex",
}

GB_PATH = Path("data/cities/gb.json")
data = json.loads(GB_PATH.read_text(encoding="utf-8"))

priority_count = 0
found = []
for city in data["cities"]:
    if city["slug"] in PRIORITY_REGIONS:
        city["priority"] = True
        priority_count += 1
        found.append(city["slug"])
    else:
        city["priority"] = False

GB_PATH.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"✅ Пріоритетних: {priority_count}")
print(f"   Решта: {len(data['cities']) - priority_count}")
print()
print("Знайдені пріоритетні:")
for slug in sorted(found):
    print(f"  • {slug}")

missing = PRIORITY_REGIONS - set(found)
if missing:
    print()
    print("⚠️ Відсутні (можна не додавати):")
    for slug in sorted(missing):
        print(f"  • {slug}")
