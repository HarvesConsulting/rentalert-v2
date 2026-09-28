"""Отримує 14 країв Чехії з boundary через Overpass API."""

import json
from pathlib import Path

from curl_cffi import requests as cffi_requests

OVERPASS_ENDPOINTS = [
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

QUERY = """
[out:json][timeout:120];
area["ISO3166-1"="CZ"][admin_level=2]->.cz;
relation["admin_level"="4"]["boundary"="administrative"](area.cz);
out tags geom;
"""

OUTPUT = Path("data/raw/cz_regions_boundaries.json")


def fetch(endpoint: str) -> dict:
    response = cffi_requests.post(
        endpoint,
        data={"data": QUERY},
        timeout=180,
        impersonate="chrome120",
        headers={"User-Agent": "rentalert-bot/1.0"},
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        print(f"🔗 Пробую: {endpoint}")
        try:
            data = fetch(endpoint)
            elements = data.get("elements", [])
            print(f"   ✅ Отримано {len(elements)} регіонів")

            if not elements:
                raise ValueError("Порожня відповідь")

            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"   💾 Збережено: {OUTPUT}")

            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name")
                print(f"      • {name} (id={el.get('id')})")
            return

        except Exception as e:
            last_error = e
            print(f"   ❌ {e}")

    print(f"❌ Всі сервери не відповіли. Остання помилка: {last_error}")


if __name__ == "__main__":
    main()
