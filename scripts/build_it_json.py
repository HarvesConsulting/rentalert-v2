"""Генерує data/cities/it.json з wikicasa_cities_found.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "wikicasa_cities_found.json"
OUT = ROOT / "data" / "cities" / "it.json"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Немає {SRC}")

    cities = json.loads(SRC.read_text(encoding="utf-8"))

    # Сортуємо: спочатку priority, потім за назвою
    cities.sort(key=lambda c: (not c.get("priority"), c["name"]))

    data = {"country": "it", "cities": cities}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Записано {len(cities)} міст → {OUT}")


if __name__ == "__main__":
    main()
