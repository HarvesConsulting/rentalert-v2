"""Генерує data/cities/cz.json зі списку всіх міст Чехії.

Джерело: Nominatim API (OpenStreetMap) — пошук за країною "cz".
Фільтр: тільки relation (міста), без селищ.

Rate limit: 1 запит/сек.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": "rentalert-bot/1.0 (contact: your@email.com)",
    "Accept-Language": "cs,en",
}
OUTPUT_PATH = Path("data/cities/cz.json")

# Спробуємо отримати всі міста через пошук
# Nominatim не дає повного списку, тому використаємо кілька стратегій


def search_city(city_name: str) -> dict | None:
    """Шукає місто в Nominatim і повертає OSM relation ID."""
    params = {
        "q": city_name,
        "format": "json",
        "countrycodes": "cz",
        "limit": 5,
        "featuretype": "city",
    }
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        results = r.json()
        for res in results:
            if res.get("osm_type") == "relation":
                return {
                    "name": res.get("display_name", city_name).split(",")[0],
                    "osm_id": f"R{res['osm_id']}",
                    "lat": float(res.get("lat", 0)),
                    "lng": float(res.get("lon", 0)),
                }
    except Exception:
        pass
    return None


def main():
    # Список назв міст з офіційного реєстру ČSÚ (вручну зібраний)
    # Це НЕ повний список 610 міст, але достатній для старту.
    # Повний список можна взяти з https://www.csu.gov.cz/
    city_names = [
        # 50 найбільших (за ČSÚ 2024)
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
        "Zlín",
        "Kladno",
        "Havířov",
        "Most",
        "Opava",
        "Frýdek-Místek",
        "Jihlava",
        "Teplice",
        "Karviná",
        "Děčín",
        "Chomutov",
        "Karlovy Vary",
        "Jablonec nad Nisou",
        "Mladá Boleslav",
        "Prostějov",
        "Přerov",
        "Česká Lípa",
        "Třebíč",
        "Tábor",
        "Znojmo",
        "Příbram",
        "Cheb",
        "Kolín",
        "Trutnov",
        "Kroměříž",
        "Šumperk",
        "Vsetín",
        "Valašské Meziříčí",
        "Litoměřice",
        "Havlíčkův Brod",
        "Hodonín",
        "Český Těšín",
        "Krnov",
        "Litvínov",
        "Jindřichův Hradec",
        "Vyškov",
        "Blansko",
        "Břeclav",
        "Žatec",
        "Louny",
        # Додайте решту міст сюди вручну або завантажте з CSV
    ]

    cities = []
    for i, name in enumerate(city_names, 1):
        print(f"[{i}/{len(city_names)}] {name}...", end=" ")
        info = search_city(name)
        if info:
            cities.append(
                {
                    "slug": name.lower()
                    .replace(" ", "-")
                    .replace("á", "a")
                    .replace("č", "c")
                    .replace("ď", "d")
                    .replace("é", "e")
                    .replace("ě", "e")
                    .replace("í", "i")
                    .replace("ň", "n")
                    .replace("ó", "o")
                    .replace("ř", "r")
                    .replace("š", "s")
                    .replace("ť", "t")
                    .replace("ú", "u")
                    .replace("ů", "u")
                    .replace("ý", "y")
                    .replace("ž", "z"),
                    "name": info["name"],
                    "region": "",  # буде порожнім, заповнимо окремо
                    "priority": i <= 10,
                    "refs": {"bezrealitky": info["osm_id"]},
                }
            )
            print(f"✅ {info['osm_id']}")
        else:
            print("❌")
        time.sleep(1.1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"country": "cz", "cities": cities}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n💾 Збережено {len(cities)} міст у {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
