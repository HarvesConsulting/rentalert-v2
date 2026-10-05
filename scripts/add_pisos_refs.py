"""Додає refs.pisos для всіх пріоритетних міст Іспанії в es.json."""

from __future__ import annotations

import json
from pathlib import Path

CITIES_PATH = Path("data/cities/es.json")

# Міста, у яких slug на Pisos.com відрізняється від slug у каталозі
PISOS_SLUG_OVERRIDES: dict[str, str] = {
    "madrid": "madrid_capital_zona_urbana",
    "gijon": "gijon_concejo_xixon_conceyu_gijon",
}


def main() -> None:
    data = json.loads(CITIES_PATH.read_text(encoding="utf-8"))

    added = 0
    for city in data["cities"]:
        if not city.get("priority"):
            continue  # пропускаємо неприоритетні

        slug = city["slug"]
        refs = city.setdefault("refs", {})

        if "pisos" in refs:
            continue  # вже додано

        # Використовуємо override, якщо є, інакше — просто slug
        pisos_slug = PISOS_SLUG_OVERRIDES.get(slug, slug)
        refs["pisos"] = pisos_slug
        added += 1
        print(f"  + {slug:20} → pisos: {pisos_slug}")

    CITIES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ Додано pisos для {added} міст")


if __name__ == "__main__":
    main()
