"""Оновлює data/cities/ro.json — додає refs.storia_ro для знайдених міст.

Запуск:
    python scripts/apply_storia_slugs.py --dry-run   # подивитись, що буде
    python scripts/apply_storia_slugs.py             # записати
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITIES_FILE = ROOT / "data" / "cities" / "ro.json"
MAP_FILE = ROOT / "scripts" / "storia_slug_map.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not MAP_FILE.exists():
        raise SystemExit(f"Немає {MAP_FILE} — спочатку запусти map_storia_slugs.py")
    if not CITIES_FILE.exists():
        raise SystemExit(f"Немає {CITIES_FILE}")

    slug_map = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    cities_data = json.loads(CITIES_FILE.read_text(encoding="utf-8"))

    ready: dict[str, str] = {
        city_slug: info["storia_slug"]
        for city_slug, info in slug_map.items()
        if info.get("storia_slug")
    }

    print(f"Маємо {len(ready)} готових storia_slug")
    print()

    changed = 0
    skipped_exists = 0
    not_in_map = 0

    for city in cities_data["cities"]:
        slug = city["slug"]

        if slug not in ready:
            not_in_map += 1
            continue

        refs = city.setdefault("refs", {})
        if "storia_ro" in refs:
            skipped_exists += 1
            continue

        refs["storia_ro"] = ready[slug]
        changed += 1
        if changed <= 40:
            print(f"  + {slug:<25} storia_ro = {ready[slug]!r}")

    print()
    print(f"Оновлено: {changed}")
    print(f"Вже було: {skipped_exists}")
    print(f"Немає в map: {not_in_map}")

    if args.dry_run:
        print()
        print("DRY RUN — файл не змінено")
        return

    if changed == 0:
        print()
        print("Немає змін — файл не перезаписуємо")
        return

    backup = CITIES_FILE.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(CITIES_FILE, backup)
    print(f"\nБекап: {backup.name}")

    CITIES_FILE.write_text(
        json.dumps(cities_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Записано: {CITIES_FILE}")


if __name__ == "__main__":
    main()
