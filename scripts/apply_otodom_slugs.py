"""Додає otodom_pl у refs польських міст.

Мапить за НАЗВОЮ міста (бо більшість Otodom-міст мають slug olx_pl_XXX).

Запуск:
    python scripts/apply_otodom_slugs.py --dry-run
    python scripts/apply_otodom_slugs.py
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PL_FILE = ROOT / "data" / "cities" / "pl.json"
MAP_FILE = ROOT / "scripts" / "otodom_cities_map.json"


def normalize(name: str) -> str:
    """'Bielsko-Biała' → 'bielskobiala', 'Częstochowa' → 'czestochowa'."""
    name = name.replace("ł", "l").replace("Ł", "L")
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "", name)
    return name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not MAP_FILE.exists():
        raise SystemExit(f"Немає {MAP_FILE}. Запусти scripts/check_otodom_cities.py")
    if not PL_FILE.exists():
        raise SystemExit(f"Немає {PL_FILE}")

    otodom_map = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    data = json.loads(PL_FILE.read_text(encoding="utf-8"))

    # Мапа: нормалізована назва → otodom_slug
    name_to_otodom = {normalize(info["name"]): info["otodom_slug"] for info in otodom_map.values()}
    print(f"Маємо {len(name_to_otodom)} Otodom-міст для мапінгу")

    changed = 0
    already = 0
    matched_names: set[str] = set()

    for city in data["cities"]:
        name_norm = normalize(city["name"])
        if name_norm not in name_to_otodom:
            continue

        matched_names.add(name_norm)
        refs = city.setdefault("refs", {})
        if "otodom_pl" in refs:
            already += 1
            continue

        refs["otodom_pl"] = name_to_otodom[name_norm]
        changed += 1
        print(
            f"  + {city['slug']:<20} {city['name']:<25} → otodom_pl = {name_to_otodom[name_norm]!r}"
        )

    # Які Otodom-міста НЕ знайдені в pl.json
    unmatched = [
        info["name"] for info in otodom_map.values() if normalize(info["name"]) not in matched_names
    ]

    print()
    print(f"Оновлено: {changed}")
    print(f"Вже було: {already}")
    if unmatched:
        print(f"Не знайдено в pl.json: {unmatched}")

    if args.dry_run:
        print("\nDRY RUN — файл не змінено")
        return

    if changed == 0:
        print("\nНемає змін")
        return

    backup = PL_FILE.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(PL_FILE, backup)
    print(f"\nБекап: {backup.name}")

    PL_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Записано: {PL_FILE}")


if __name__ == "__main__":
    main()
