"""Генерація data/cities/gb.json для OpenRent.

1. Парсимо сторінку OpenRent зі списком усіх локацій
2. Витягуємо назви (Aberdeenshire, Adur, ...)
3. Генеруємо slug (aberdeenshire, adur, ...)
4. Зберігаємо в data/cities/gb.json
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers

# ─────────────────────────────────────────────────────────────
# Налаштування
# ─────────────────────────────────────────────────────────────

URL = "https://www.openrent.co.uk/search-for-properties-to-rent-by-county-or-borough"
OUTPUT_PATH = Path("data/cities/gb.json")


def _normalize(text: str) -> str:
    """Нормалізація: lower + видалення діакритики."""
    if not text:
        return ""
    s = str(text).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def make_slug(name: str) -> str:
    """Робить slug з назви локації.

    Приклад:
        "Amber Valley" → "amber-valley"
        "Argyll (Argyllshire)" → "argyll-argyllshire"
        "Wyre Forest" → "wyre-forest"
    """
    s = _normalize(name)
    # Замінюємо пробіли, апострофи, дужки на дефіси
    s = re.sub(r"[\s'()]+", "-", s)
    # Прибираємо всі не-словесні символи, крім дефісів
    s = re.sub(r"[^\w-]", "", s)
    # Прибираємо множинні дефіси
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def fetch_locations() -> list[str]:
    """Парсить сторінку OpenRent і повертає список локацій."""
    print(f"📥 Завантажую {URL}...")
    r = cffi_requests.get(
        URL,
        impersonate="chrome",
        headers=stealth_headers(),
        timeout=30,
    )
    print(f"   Status: {r.status_code}, Size: {len(r.text)}")

    if r.status_code != 200:
        print(f"   ❌ HTTP {r.status_code}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Шукаємо всі посилання на локації
    # Формат: <a href="/properties-to-rent/aberdeenshire">Properties to rent in Aberdeenshire</a>
    locations: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Фільтруємо тільки посилання на локації
        if not href.startswith("/properties-to-rent/"):
            continue

        # Витягуємо назву з тексту
        text = a.get_text(strip=True)
        # "Properties to rent in Aberdeenshire" → "Aberdeenshire"
        match = re.search(r"in\s+(.+)$", text, re.IGNORECASE)
        name = match.group(1).strip() if match else ""

        if not name:
            continue

        # Генеруємо slug з НАЗВИ (а не з URL!)
        slug = make_slug(name)
        if not slug or slug in seen:
            continue
        seen.add(slug)

        locations.append(
            {
                "slug": slug,
                "name": name,
            }
        )

    print(f"   ✅ Знайдено {len(locations)} локацій")
    return locations


def main() -> None:
    locations = fetch_locations()

    if not locations:
        print("❌ Не вдалося отримати локації")
        return

    # Формуємо cities
    cities = []
    for loc in locations:
        cities.append(
            {
                "slug": loc["slug"],
                "name": loc["name"],
                "region": "",
                "priority": True,  # всі локації з OpenRent — priority
                "refs": {"openrent": loc["slug"]},
            }
        )

    # Зберігаємо
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"country": "gb", "cities": cities},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"✅ Готово: {len(cities)} локацій у {OUTPUT_PATH}")
    print()
    print("Перші 10:")
    for c in cities[:10]:
        print(f"  {c['name']} ({c['slug']})")
    print()
    print("Останні 10:")
    for c in cities[-10:]:
        print(f"  {c['name']} ({c['slug']})")


if __name__ == "__main__":
    main()
