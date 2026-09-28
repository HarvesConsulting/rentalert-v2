"""Заповнює region для всіх 831 чеського міста через Nominatim.

Використовує кеш (data/raw/cz_regions_cache.json), щоб не робити
повторних запитів при перезапуску.

Rate limit: 1.1 секунди між запитами.
Орієнтовний час: ~15 хвилин для 831 міста.
"""

import json
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": "rentalert-bot/1.0 (contact: your@email.com)",
    "Accept-Language": "cs,en",
}

CZ_PATH = Path("data/cities/cz.json")
CACHE_PATH = Path("data/raw/cz_regions_cache.json")

# Всі офіційні краї Чехії
KRAJE = {
    "Hlavní město Praha",
    "Středočeský kraj",
    "Jihočeský kraj",
    "Plzeňský kraj",
    "Karlovarský kraj",
    "Ústecký kraj",
    "Liberecký kraj",
    "Královéhradecký kraj",
    "Pardubický kraj",
    "Kraj Vysočina",
    "Jihomoravský kraj",
    "Olomoucký kraj",
    "Zlínský kraj",
    "Moravskoslezský kraj",
}


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def lookup_region(city_name: str) -> str | None:
    """Знаходить край для міста через Nominatim."""
    params = {
        "q": city_name,
        "format": "json",
        "countrycodes": "cz",
        "limit": 5,
        "featuretype": "city",
        "accept-language": "cs",
        "addressdetails": 1,
    }
    try:
        r = cffi_requests.get(
            NOMINATIM,
            params=params,
            headers=HEADERS,
            timeout=15,
            impersonate="chrome120",
        )
        if r.status_code != 200:
            return None

        results = r.json()
        if not results:
            return None

        # Дивимось у address різних результатів
        for res in results:
            address = res.get("address", {})
            # Шукаємо поле, яке відповідає краю
            for field in ("state", "region", "county"):
                value = address.get(field)
                if value and value in KRAJE:
                    return value
            # Іноді край у display_name
            display = res.get("display_name", "")
            for part in display.split(","):
                part = part.strip()
                if part in KRAJE:
                    return part
        return None
    except Exception:
        return None


def main() -> None:
    if not CZ_PATH.exists():
        print(f"❌ {CZ_PATH} не знайдено")
        return

    data = json.loads(CZ_PATH.read_text(encoding="utf-8"))
    cities = data["cities"]
    cache = load_cache()

    print(f"📋 Міст: {len(cities)}")
    print(f"💾 Кеш: {len(cache)} записів\n")

    updated = 0
    already = 0
    failed = 0

    for i, city in enumerate(cities, 1):
        name = city["name"]

        # Пропускаємо, якщо регіон вже заповнено
        if city.get("region"):
            already += 1
            continue

        # Перевіряємо кеш
        if name in cache:
            region = cache[name]
            if region:
                city["region"] = region
                updated += 1
            continue

        # Запит до Nominatim
        region = lookup_region(name)
        cache[name] = region

        if region:
            city["region"] = region
            updated += 1
            print(f"  [{i:>3}] ✅ {name} → {region}")
        else:
            failed += 1
            print(f"  [{i:>3}] ❌ {name}")

        # Зберігаємо кеш кожні 20 запитів
        if i % 20 == 0:
            save_cache(cache)
            print(f"       💾 Кеш збережено ({len(cache)} записів)")

        time.sleep(1.1)  # Nominatim rate limit

    # Фінальне збереження
    save_cache(cache)
    CZ_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print(f"✅ Оновлено:      {updated}")
    print(f"⏭  Вже мало регіон: {already}")
    print(f"❌ Не знайдено:    {failed}")
    print(f"💾 Кеш:          {CACHE_PATH}")


if __name__ == "__main__":
    main()
