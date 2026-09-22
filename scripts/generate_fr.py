"""Генерація data/cities/fr.json для Bien'ici.

1. Беремо топ-N комун з geo.api.gouv.fr
2. Для кожної — suggest.json Bien'ici → zoneId
3. Зберігаємо в data/cities/fr.json

Кешує результати в scripts/.cache_fr.json — щоб не перезапитувати.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests

# ─────────────────────────────────────────────────────────────
# Налаштування
# ─────────────────────────────────────────────────────────────

TOP_N = 5000
DELAY = 0.8
CACHE_PATH = Path("scripts/.cache_fr.json")
OUTPUT_PATH = Path("data/cities/fr.json")


# ─────────────────────────────────────────────────────────────
# Крок 1: отримати топ-N комун
# ─────────────────────────────────────────────────────────────


def fetch_top_communes(n: int) -> list[dict]:
    """Повертає топ-N комун за населенням."""
    print("📥 Завантажую комуни з geo.api.gouv.fr...")
    r = cffi_requests.get(
        "https://geo.api.gouv.fr/communes",
        params={
            "fields": "nom,code,codesPostaux,population",
            "format": "json",
        },
        impersonate="chrome",
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    print(f"✅ Отримано {len(data)} комун")

    data = [c for c in data if c.get("population", 0) > 0]
    data.sort(key=lambda c: c.get("population", 0), reverse=True)

    top = data[:n]
    print(
        f"📊 Топ-{n}: від {top[0]['nom']} ({top[0]['population']} осіб) "
        f"до {top[-1]['nom']} ({top[-1]['population']} осіб)"
    )
    return top


# ─────────────────────────────────────────────────────────────
# Крок 2: отримати zoneId через suggest.json
# ─────────────────────────────────────────────────────────────


def load_cache() -> dict:
    """Завантажує кеш zoneId."""
    if CACHE_PATH.exists():
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    """Зберігає кеш zoneId."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch_zone_id(insee_code: str, city_name: str) -> str | None:
    """Повертає zoneId для комуни через suggest.json.

    ВАЖЛИВО: suggest.json не знає INSEE-кодів, тому передаємо НАЗВУ.
    Потім фільтруємо за insee_code і type=city.
    """
    try:
        r = cffi_requests.get(
            "https://res.bienici.com/suggest.json",
            params={"q": city_name},
            impersonate="chrome",
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None

        # Пріоритет 1: точний збіг за insee_code і type=city
        for item in data:
            if item.get("insee_code") == insee_code and item.get("type") == "city":
                zone_ids = item.get("zoneIds", [])
                if zone_ids:
                    return zone_ids[0]

        # Пріоритет 2: type=city, назва збігається
        for item in data:
            if item.get("type") == "city" and item.get("name") == city_name:
                zone_ids = item.get("zoneIds", [])
                if zone_ids:
                    return zone_ids[0]

        # Немає точного збігу — пропускаємо
        return None
    except Exception as e:
        print(f"    ⚠️ {city_name} ({insee_code}): {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Крок 3: генерація fr.json
# ─────────────────────────────────────────────────────────────


def make_slug(name: str, insee: str) -> str:
    """Робить slug з назви міста + INSEE-код (для унікальності)."""
    s = name.lower()
    replacements = {
        " ": "-",
        "'": "",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "ô": "o",
        "ö": "o",
        "î": "i",
        "ï": "i",
        "û": "u",
        "ù": "u",
        "ü": "u",
        "ç": "c",
        "œ": "oe",
        "æ": "ae",
        "ÿ": "y",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    return f"{s}-{insee}"


def main() -> None:
    top = fetch_top_communes(TOP_N)
    cache = load_cache()
    print(f"📦 Кеш: {len(cache)} записів")

    cities = []
    total = len(top)
    for i, commune in enumerate(top, 1):
        insee = commune["code"]
        name = commune["nom"]
        population = commune.get("population", 0)

        if insee in cache:
            zone_id = cache[insee]
        else:
            zone_id = fetch_zone_id(insee, name)
            cache[insee] = zone_id
            time.sleep(DELAY)

            if i % 50 == 0:
                save_cache(cache)
                print(f"  ... {i}/{total} (кеш збережено)")

        if not zone_id:
            continue

        cities.append(
            {
                "slug": make_slug(name, insee),
                "name": name,
                "region": "",
                "priority": population >= 50_000,
                "refs": {"bienici": zone_id},
            }
        )

    save_cache(cache)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"country": "fr", "cities": cities},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"✅ Готово: {len(cities)} міст у {OUTPUT_PATH}")
    print(f"📦 Кеш: {len(cache)} записів у {CACHE_PATH}")


if __name__ == "__main__":
    main()
