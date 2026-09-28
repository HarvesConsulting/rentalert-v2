"""Виправляє refs.bezrealitky у cz.json:
1. Прибирає префікс 'R' (парсер сам його додає).
2. Замінює старі OSM ID на правильні (краї замість міст).
"""

import json
from pathlib import Path

CZ_PATH = Path("data/cities/cz.json")
data = json.loads(CZ_PATH.read_text(encoding="utf-8"))

# Правильні OSM ID (краї) для 14 регіонів Чехії — з czechRegions GraphQL
REGION_OSM_IDS = {
    "Jihočeský kraj": "442321",
    "Jihomoravský kraj": "442311",
    "Karlovarský kraj": "442314",
    "Kraj Vysočina": "442453",
    "Královéhradecký kraj": "442463",
    "Liberecký kraj": "442455",
    "Moravskoslezský kraj": "442461",
    "Olomoucký kraj": "442459",
    "Pardubický kraj": "442460",
    "Plzeňský kraj": "442466",
    "Praha": "435514",
    "Středočeský kraj": "442397",
    "Ústecký kraj": "442452",
    "Zlínský kraj": "442449",
}

# Спеціальні випадки: стара назва → правильний ID краю
CITY_TO_REGION = {
    "praha": "Praha",
    "brno": "Jihomoravský kraj",
    "ostrava": "Moravskoslezský kraj",
    "plzen": "Plzeňský kraj",
    "liberec": "Liberecký kraj",
    "olomouc": "Olomoucký kraj",
    "ceske-budejovice": "Jihočeský kraj",
    "hradec-kralove": "Královéhradecký kraj",
    "pardubice": "Pardubický kraj",
    "usti-nad-labem": "Ústecký kraj",
    "zlin": "Zlínský kraj",
}

fixed_r = 0
fixed_id = 0
fixed_region = 0

for city in data["cities"]:
    refs = city.get("refs", {})
    old = refs.get("bezrealitky")
    if old is None:
        continue

    # 1. Прибираємо префікс R
    if isinstance(old, str) and old.startswith("R"):
        old = old[1:]
        fixed_r += 1

    # 2. Для топ-міст — ставимо OSM ID їхнього краю
    slug = city["slug"]
    if slug in CITY_TO_REGION:
        region_name = CITY_TO_REGION[slug]
        new_id = REGION_OSM_IDS.get(region_name, old)
        if new_id != old:
            fixed_id += 1
        refs["bezrealitky"] = new_id
    else:
        # Решта міст — залишаємо OSM ID міста (без R)
        refs["bezrealitky"] = old
        fixed_region += 1

CZ_PATH.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"✅ Прибрано префікс R: {fixed_r} міст")
print(f"✅ Оновлено OSM ID топ-міст на край: {fixed_id} міст")
print(f"✅ Решта міст (OSM ID міста): {fixed_region} міст")
print(f"\n💾 Збережено в {CZ_PATH}")
