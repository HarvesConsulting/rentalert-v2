"""Мержит scripts/storia_slug_map.json → data/cities/ro.json.

Ключі в обох файлах збігаються 1:1 (city.slug == key в slug_map).
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
RO_CITIES = ROOT / "data" / "cities" / "ro.json"
SLUG_MAP = ROOT / "scripts" / "storia_slug_map.json"


def main() -> None:
    if not RO_CITIES.exists():
        raise SystemExit(f"❌ Не знайдено {RO_CITIES}")
    if not SLUG_MAP.exists():
        raise SystemExit(f"❌ Не знайдено {SLUG_MAP}")

    doc = json.loads(RO_CITIES.read_text(encoding="utf-8"))
    slug_map = json.loads(SLUG_MAP.read_text(encoding="utf-8"))

    valid: dict[str, str] = {
        key: entry["storia_slug"] for key, entry in slug_map.items() if entry.get("storia_slug")
    }
    print(f"📖 Всього в slug_map: {len(slug_map)}")
    print(f"✅ Валідних storia_slug: {len(valid)}")

    updated = 0
    for city in doc["cities"]:
        slug = city["slug"]
        storia_slug = valid.get(slug)
        if not storia_slug:
            continue
        city.setdefault("refs", {})["storia_ro"] = storia_slug
        updated += 1

    ro_slugs = {c["slug"] for c in doc["cities"]}
    orphan = [s for s in valid if s not in ro_slugs]

    print(f"📝 Оновлено City: {updated}")
    if orphan:
        print(f"⚠️  Orphan (є в map, немає в ro.json): {len(orphan)}")
        for s in orphan[:20]:
            print(f"     {s}")
    else:
        print("✅ Orphan немає")

    RO_CITIES.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"💾 Записано: {RO_CITIES}")


if __name__ == "__main__":
    main()
