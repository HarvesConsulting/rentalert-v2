"""Заповнює region для 10 топових чеських міст."""

import json
from pathlib import Path

CITY_TO_REGION = {
    "Praha": "Hlavní město Praha",
    "Brno": "Jihomoravský kraj",
    "Ostrava": "Moravskoslezský kraj",
    "Plzeň": "Plzeňský kraj",
    "Liberec": "Liberecký kraj",
    "Olomouc": "Olomoucký kraj",
    "České Budějovice": "Jihočeský kraj",
    "Hradec Králové": "Královéhradecký kraj",
    "Pardubice": "Pardubický kraj",
    "Ústí nad Labem": "Ústecký kraj",
}

CZ_PATH = Path("data/cities/cz.json")
data = json.loads(CZ_PATH.read_text(encoding="utf-8"))

updated = 0
for city in data["cities"]:
    if city["name"] in CITY_TO_REGION:
        city["region"] = CITY_TO_REGION[city["name"]]
        updated += 1
        print(f"  ✓ {city['name']}: {city['region']}")

CZ_PATH.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"\n✅ Оновлено: {updated} міст")
