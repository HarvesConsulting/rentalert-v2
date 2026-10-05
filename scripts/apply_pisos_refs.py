"""Додає refs.pisos для всіх міст, де Pisos.com працює."""

from __future__ import annotations

import json
from pathlib import Path

CITIES_PATH = Path("data/cities/es.json")
FOUND_PATH = Path("scripts/pisos_slugs_found.json")


def main() -> None:
    cities_data = json.loads(CITIES_PATH.read_text(encoding="utf-8"))
    found_data = json.loads(FOUND_PATH.read_text(encoding="utf-8"))
    found: dict[str, str] = found_data["found"]

    added = 0
    skipped = 0

    for city in cities_data["cities"]:
        slug = city["slug"]
        refs = city.setdefault("refs", {})

        # Pisos не працює для цього міста — пропускаємо
        if slug not in found:
            if "pisos" in refs:
                del refs["pisos"]  # прибираємо, якщо було додано помилково
                print(f"  − {slug:28} (видалено pisos)")
                skipped += 1
            continue

        pisos_slug = found[slug]

        if refs.get("pisos") == pisos_slug:
            continue  # вже є

        refs["pisos"] = pisos_slug
        added += 1

    CITIES_PATH.write_text(
        json.dumps(cities_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n✅ Додано refs.pisos для {added} міст")
    print(f"⏭ Пропущено (не працюють): {skipped}")


if __name__ == "__main__":
    main()
