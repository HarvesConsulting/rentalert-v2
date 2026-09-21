"""Витягує список міст Хорватії з NJUSKALO.

Алгоритм:
1. Беремо сторінку /iznajmljivanje-stanova (без регіону) — там список жупаній.
2. Для кожної жупанії — беремо сторінку /iznajmljivanje-stanova/{županija}.
3. Витягуємо всі посилання на міста (format: /iznajmljivanje-stanova/{city}).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

BASE = "https://www.njuskalo.hr"
OUT = Path(__file__).parent.parent / "data" / "raw" / "hr_njuskalo_cities.json"


def fetch(url: str) -> str:
    resp = requests.get(url, impersonate="chrome", timeout=30)
    if resp.status_code != 200:
        print(f"  ❌ HTTP {resp.status_code}: {url}")
        return ""
    return resp.text


def extract_cities(html: str, exclude_slug: str) -> dict[str, str]:
    """Витягує {slug: name} з HTML."""
    soup = BeautifulSoup(html, "html.parser")
    cities: dict[str, str] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not text:
            continue

        path = urlparse(href).path.strip("/")
        parts = path.split("/")
        if len(parts) == 2 and parts[0] == "iznajmljivanje-stanova":
            slug = parts[1]
            if slug == exclude_slug:
                continue
            if slug not in cities:
                cities[slug] = text

    return cities


def main() -> None:
    # 1. Жупанії
    print("📡 Fetching županije...")
    html = fetch(f"{BASE}/iznajmljivanje-stanova")
    if not html:
        return

    soup = BeautifulSoup(html, "html.parser")
    regions: dict[str, str] = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not text:
            continue

        path = urlparse(href).path.strip("/")
        parts = path.split("/")
        if len(parts) == 2 and parts[0] == "iznajmljivanje-stanova":
            slug = parts[1]
            if slug not in regions:
                regions[slug] = text

    print(f"  ✅ {len(regions)} županija\n")

    # 2. Для кожної жупанії — міста
    all_cities: dict[str, str] = {}

    for i, (region_slug, region_name) in enumerate(sorted(regions.items()), 1):
        print(f"[{i}/{len(regions)}] {region_name} ({region_slug})...")

        time.sleep(1)  # rate limit
        html = fetch(f"{BASE}/iznajmljivanje-stanova/{region_slug}")
        if not html:
            continue

        cities = extract_cities(html, exclude_slug=region_slug)
        print(f"  → {len(cities)} міст")

        for slug, name in cities.items():
            if slug not in all_cities:
                all_cities[slug] = name

    print(f"\n✅ Всього міст: {len(all_cities)}")

    # 3. Зберегти
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(
            {
                "regions": regions,
                "cities": all_cities,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"✅ Збережено: {OUT}")

    # 4. Показати приклад
    print("\n📍 Перші 20 міст:")
    for slug, name in sorted(all_cities.items())[:20]:
        print(f"  {slug:30s} → {name}")


if __name__ == "__main__":
    main()
