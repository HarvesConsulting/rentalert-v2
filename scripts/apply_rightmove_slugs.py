"""Додає rightmove у refs UK графств/міст.

Читає scripts/rightmove_counties.json (результат check_rightmove_counties.py).

Запуск:
    python scripts/apply_rightmove_slugs.py --dry-run
    python scripts/apply_rightmove_slugs.py
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GB_FILE = ROOT / "data" / "cities" / "gb.json"
MAP_FILE = ROOT / "scripts" / "rightmove_counties.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not MAP_FILE.exists():
        raise SystemExit(f"Немає {MAP_FILE}. Запусти scripts/check_rightmove_counties.py")
    if not GB_FILE.exists():
        raise SystemExit(f"Немає {GB_FILE}")

    counties_map = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    data = json.loads(GB_FILE.read_text(encoding="utf-8"))

    changed = 0
    already = 0
    matched_slugs: set[str] = set()

    for city in data["cities"]:
        slug = city["slug"]
        if slug not in counties_map:
            continue

        matched_slugs.add(slug)
        refs = city.setdefault("refs", {})
        if "rightmove" in refs:
            already += 1
            continue

        # Rightmove ідентифікатори мають формат REGION^XXXXX
        rm_id = counties_map[slug]["rightmove_id"]
        if not str(rm_id).startswith("REGION"):
            rm_id = f"REGION^{rm_id}"

        refs["rightmove"] = rm_id
        changed += 1
        print(f"  + {slug:<20} rightmove = {rm_id!r}")

    unmatched = [s for s in counties_map if s not in matched_slugs]

    print()
    print(f"Оновлено: {changed}")
    print(f"Вже було: {already}")
    if unmatched:
        print(f"Немає в gb.json: {unmatched}")

    if args.dry_run:
        print("\nDRY RUN — файл не змінено")
        return

    if changed == 0:
        print("\nНемає змін")
        return

    backup = GB_FILE.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(GB_FILE, backup)
    print(f"\nБекап: {backup.name}")

    GB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Записано: {GB_FILE}")


if __name__ == "__main__":
    main()
