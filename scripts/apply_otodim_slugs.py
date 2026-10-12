"""Додає otodim_ua у refs обласних центрів України.

Запуск:
    python scripts/apply_otodim_slugs.py --dry-run
    python scripts/apply_otodim_slugs.py
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA_FILE = ROOT / "data" / "cities" / "ua.json"

CITY_TO_OTODIM = {
    "kyiv": "kyiv",
    "lviv": "lvivska-oblast",
    "odesa": "odeska-oblast",
    "kharkiv": "kharkivska-oblast",
    "dnipro": "dnipropetrovska-oblast",
    "vinnytsia": "vinnytska-oblast",
    "lutsk": "volynska-oblast",
    "zhytomyr": "zhytomyrska-oblast",
    "uzhhorod": "zakarpatska-oblast",
    "zaporizhzhia": "zaporizka-oblast",
    "kropyvnytskyi": "kirovohradska-oblast",
    "mykolaiv": "mykolaivska-oblast",
    "poltava": "poltavska-oblast",
    "rivne": "rivnenska-oblast",
    "sumy": "sumska-oblast",
    "ternopil": "ternopilska-oblast",
    "kherson": "khersonska-oblast",
    "khmelnytskyi": "khmelnytska-oblast",
    "cherkasy": "cherkaska-oblast",
    "chernivtsi": "chernivetska-oblast",
    "chernihiv": "chernihivska-oblast",
    "donetsk": "donetska-oblast",
    "ivano-frankivsk": "ivano-frankivska-oblast",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = json.loads(UA_FILE.read_text(encoding="utf-8"))
    cities = data["cities"]

    changed = 0
    already = 0

    for city in cities:
        slug = city["slug"]
        if slug not in CITY_TO_OTODIM:
            continue

        refs = city.setdefault("refs", {})
        if "otodim_ua" in refs:
            already += 1
            continue

        refs["otodim_ua"] = CITY_TO_OTODIM[slug]
        changed += 1
        print(f"  + {slug:<20} otodim_ua = {CITY_TO_OTODIM[slug]!r}")

    existing = {c["slug"] for c in cities}
    not_found = [s for s in CITY_TO_OTODIM if s not in existing]

    print()
    print(f"Оновлено: {changed}")
    print(f"Вже було: {already}")
    if not_found:
        print(f"Не знайдено в ua.json: {not_found}")

    if args.dry_run:
        print("\nDRY RUN — файл не змінено")
        return

    if changed == 0:
        print("\nНемає змін")
        return

    backup = UA_FILE.with_suffix(f".json.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(UA_FILE, backup)
    print(f"\nБекап: {backup.name}")

    UA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Записано: {UA_FILE}")


if __name__ == "__main__":
    main()
