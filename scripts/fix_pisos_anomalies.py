"""Шукає правильні slug Pisos.com для міст, де стандартний slug не працює."""

from __future__ import annotations

import json
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests

CITIES_PATH = Path("data/cities/es.json")
OUTPUT_PATH = Path("scripts/pisos_anomalies_fixed.json")

# Список міст, які повернули 0 оголошень (з вашого логу)
ANOMALY_SLUGS = [
    "huelva",
    "marbella",
    "orihuela",
    "ourense",
    "sabadell",
    "tarragona",
    "valencia",
    "vigo",
    "amurrio",
    "arroyomolinos",
    "ayamonte",
    "boiro",
    "briviesca",
    "calafell",
    "coin",
    "cullera",
    "fraga",
    "fuengirola",
    "inca",
    "llucmajor",
    "madridejos",
    "manilva",
    "mislata",
    "montellano",
    "montilla",
    "moratalla",
    "ordes",
    "pinoso",
    "pozoblanco",
    "rojales",
    "santanyi",
    "sarria",
    "tomelloso",
    "torremolinos",
    "trujillo",
    "villablino",
    "villaviciosa",
    "villena",
]

# Словник суфіксів для спроби. Порядок важливий — від найімовірнішого.
SUFFIXES = [
    "",  # базовий slug
    "_capital_zona_urbana",
    "_capital",
    "_zona_urbana",
    "_concejo",  # для астурійських міст, як Gijón
]

DELAY = 0.8


def check_slug(slug: str) -> tuple[str, int]:
    """Повертає (status, кількість оголошень)."""
    url = f"https://www.pisos.com/alquiler/pisos-{slug}/"
    try:
        r = cffi_requests.get(
            url,
            impersonate="chrome",
            timeout=15,
            allow_redirects=True,
        )
        if r.status_code != 200:
            return "fail", 0
        text = r.text
        if "0 resultados" in text or "No hemos encontrado" in text:
            return "empty", 0
        count = text.count('class="ad-preview')
        return ("ok", count) if count > 0 else ("empty", 0)
    except Exception:
        return "fail", 0


def find_working_slug(base_slug: str) -> str | None:
    """Шукає робочий slug серед варіантів. Повертає None, якщо нічого не знайдено."""
    for suffix in SUFFIXES:
        candidate = f"{base_slug}{suffix}"
        status, count = check_slug(candidate)
        if status == "ok":
            print(f"    ✓ {candidate:50} → {count} огол.")
            return candidate
        elif status == "empty":
            print(f"    ○ {candidate:50} → 0 огол.")
        else:
            print(f"    ✗ {candidate:50} → 404/error")
        time.sleep(DELAY)
    return None


def main() -> None:
    fixed: dict[str, str] = {}
    not_found: list[str] = []

    total = len(ANOMALY_SLUGS)
    print(f"Шукаю правильні slug для {total} аномалій...\n")

    for i, base_slug in enumerate(ANOMALY_SLUGS, 1):
        print(f"[{i:3}/{total}] {base_slug}")
        working = find_working_slug(base_slug)
        if working:
            fixed[base_slug] = working
            print(f"  ✅ Знайдено: {working}\n")
        else:
            not_found.append(base_slug)
            print("  ❌ Не знайдено\n")

    OUTPUT_PATH.write_text(
        json.dumps({"fixed": fixed, "not_found": not_found}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 60)
    print(f"✅ Виправлено: {len(fixed)}")
    print(f"❌ Не знайдено: {len(not_found)}")
    print(f"\nРезультат: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
