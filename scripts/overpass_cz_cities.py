"""Витягує всі міста (place=city/town) Чехії через Overpass API.

Скрипт автоматично перемикається між серверами Overpass,
якщо один із них перевантажений.

Запуск:
    python scripts/overpass_cz_cities.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

# Список публічних дзеркал Overpass API (від найшвидшого до основного)
OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",  # Менш відоме, частіше вільне
    "https://overpass-api.de/api/interpreter",  # Офіційне, може бути зайняте
    "https://overpass.kumi.systems/api/interpreter",  # Резервне
]

QUERY = """
[out:json][timeout:300];
area["ISO3166-1"="CZ"]->.searchArea;
(
  relation["admin_level"="8"]["boundary"="administrative"]["place"~"city|town"](area.searchArea);
);
out body;
"""

OUTPUT_PATH = Path("data/raw/cz_overpass_cities.json")


def _slugify(name: str) -> str:
    """Створює URL-friendly slug з чеської назви."""
    # Транслітерація чеських діакритиків
    translation = str.maketrans("áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ", "acdeeinorstuuyzACDEEINORSTUUYZ")
    name = name.translate(translation).lower()
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def fetch_cities() -> list[dict]:
    """Пробує кожен сервер по черзі, поки один не спрацює."""
    last_error: Exception | None = None

    for endpoint in OVERPASS_ENDPOINTS:
        print(f"🔗 Пробую сервер: {endpoint}")
        try:
            response = requests.post(
                endpoint,
                data={"data": QUERY},
                timeout=300,
                headers={
                    "User-Agent": "rentalert-bot/1.0",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            if "elements" not in data:
                raise ValueError("Відповідь не містить 'elements'")

            print(f"   ✅ Успіх! Отримано {len(data['elements'])} об'єктів")
            return data["elements"]

        except Exception as e:
            last_error = e
            print(f"   ❌ Помилка: {e}")
            time.sleep(5)  # Пауза перед наступним сервером

    raise RuntimeError(f"Усі сервери Overpass не відповіли. Остання помилка: {last_error}")


def main() -> None:
    elements = fetch_cities()

    cities = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        cities.append(
            {
                "slug": _slugify(name),
                "name": name,
                "region": tags.get("addr:region", ""),
                "priority": False,
                "refs": {"bezrealitky": f"R{el['id']}"},
            }
        )

    # Сортуємо за назвою
    cities.sort(key=lambda c: c["name"])

    # Позначаємо 10 найбільших як пріоритетні (можна потім скоригувати)
    for city in cities[:10]:
        city["priority"] = True

    result = {
        "country": "cz",
        "cities": cities,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n💾 Збережено {len(cities)} міст у {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
