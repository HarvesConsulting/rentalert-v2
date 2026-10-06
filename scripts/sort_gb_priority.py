"""Переставляє топ-5 британських регіонів на початок gb.json.

Бот показує перші 5 пріоритетних у порядку gb.json.
Тому London, Kent, Essex, Hampshire, Lancashire мають бути першими.
"""

import json
from pathlib import Path

TOP_FIRST = [
    "london",
    "kent",
    "essex",
    "hampshire",
    "lancashire",
]

GB_PATH = Path("data/cities/gb.json")
data = json.loads(GB_PATH.read_text(encoding="utf-8"))
cities = data["cities"]

# Витягуємо топ-5
top = []
rest = []
for city in cities:
    if city["slug"] in TOP_FIRST and city.get("priority"):
        top.append(city)
    else:
        rest.append(city)

# Сортуємо top у порядку TOP_FIRST
top_sorted = sorted(top, key=lambda c: TOP_FIRST.index(c["slug"]))

# Решта: спочатку пріоритетні (за алфавітом), потім звичайні
priority_rest = sorted(
    [c for c in rest if c.get("priority")],
    key=lambda c: c["name"],
)
non_priority = sorted(
    [c for c in rest if not c.get("priority")],
    key=lambda c: c["name"],
)

data["cities"] = top_sorted + priority_rest + non_priority

GB_PATH.write_text(
    json.dumps(data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("✅ Перші 5 у gb.json:")
for c in data["cities"][:5]:
    print(f"  • {c['name']} ({c['slug']}) priority={c.get('priority')}")

print(f"\n📊 Всього: {len(data['cities'])} міст")
print(f"   Пріоритетних: {sum(1 for c in data['cities'] if c.get('priority'))}")
