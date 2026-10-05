"""Перевіряє, які міста Іспанії є на Pisos.com і мають оголошення."""

from __future__ import annotations

import json
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests

CITIES_PATH = Path("data/cities/es.json")
OUTPUT_PATH = Path("scripts/pisos_slugs_found.json")

# Міста з відомим override
PISOS_SLUG_OVERRIDES: dict[str, str] = {
    "madrid": "madrid_capital_zona_urbana",
    "gijon": "gijon_concejo_xixon_conceyu_gijon",
}

# Пауза між запитами (сек)
DELAY = 0.8


def check_slug(slug: str) -> tuple[str, int]:
    """Повертає (status, кількість оголошень).

    status:
      "ok"     — сторінка є, оголошення є
      "empty"  — сторінка є, оголошень немає
      "fail"   — 404 або помилка
    """
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

        # Рахуємо картки оголошень
        count = text.count('class="ad-preview')
        if count == 0:
            return "empty", 0
        return "ok", count
    except Exception:
        return "fail", 0


def main() -> None:
    data = json.loads(CITIES_PATH.read_text(encoding="utf-8"))
    cities = data["cities"]
    total = len(cities)

    found: dict[str, str] = {}
    empty: list[str] = []
    failed: list[str] = []

    print(f"Перевіряю {total} міст... (це займе ~{total * DELAY / 60:.1f} хв)\n")

    for i, city in enumerate(cities, 1):
        slug = city["slug"]
        pisos_slug = PISOS_SLUG_OVERRIDES.get(slug, slug)

        status, count = check_slug(pisos_slug)

        if status == "ok":
            found[slug] = pisos_slug
            print(f"[{i:3}/{total}] ✓ {slug:28} → {pisos_slug:40} ({count} огол.)")
        elif status == "empty":
            empty.append(slug)
            print(f"[{i:3}/{total}] ○ {slug:28} → {pisos_slug:40} (0 огол.)")
        else:
            failed.append(slug)
            print(f"[{i:3}/{total}] ✗ {slug:28} → 404/error")

        time.sleep(DELAY)

    OUTPUT_PATH.write_text(
        json.dumps(
            {"found": found, "empty": empty, "failed": failed},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print(f"✓ Працюють з оголошеннями: {len(found)}")
    print(f"○ Порожні:                 {len(empty)}")
    print(f"✗ Не знайдені:             {len(failed)}")
    print(f"\nРезультат: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
