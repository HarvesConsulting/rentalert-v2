"""Додає Тирасполь і Бендеры в md.json (вони є в 999.md, але не в поточному наборі)."""

import json
from pathlib import Path

# Міста, які треба додати вручну (з попереднього запуску)
MISSING = [
    {"id": 13495, "name": "Тирасполь", "region_name": "Тирасполь мун."},
    {"id": 13498, "name": "Бендеры", "region_name": "Бендеры мун."},
    {"id": 14186, "name": "Единец", "region_name": "Единцы"},
]


def main() -> None:
    path = Path("data/cities/md.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    existing_ids = {c["refs"]["999md"] for c in data["cities"]}

    added = 0
    for m in MISSING:
        if m["id"] in existing_ids:
            continue

        slug = {
            "Тирасполь": "tiraspol",
            "Бендеры": "bender",
            "Единец": "edinet",
        }.get(m["name"], m["name"].lower())

        priority = m["id"] in {13495, 13498, 14186}

        data["cities"].append(
            {
                "slug": slug,
                "name": m["name"],
                "region": m["region_name"],
                "priority": priority,
                "refs": {"999md": m["id"]},
                "aliases": [m["name"].lower()],
            }
        )
        added += 1
        print(f"  + {m['name']} ({m['id']}) → {slug}")

    # Пересортувати
    data["cities"].sort(key=lambda c: (not c["priority"], c["name"]))

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ Додано: {added}")
    print(f"Всього міст: {len(data['cities'])}")
    print(f"Priority: {sum(1 for c in data['cities'] if c['priority'])}")


if __name__ == "__main__":
    main()
