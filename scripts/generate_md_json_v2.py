"""Генерує data/cities/md.json з md_999md_cities_from_ads.json.

Додає:
  - slug з назви (транслітерація ro)
  - priority для топ-10 найбільших міст
  - aliases: ro (translated), ru (з title), + кілька ручних
"""

import json
import re
import unicodedata
from pathlib import Path

# Топ-10 пріоритетних (з тих, що ми знайшли)
PRIORITY_IDS = {
    13859,   # Кишинёв
    14247,   # Бельцы
    13495,   # Тирасполь (треба перевірити, чи є)
    13498,   # Бендеры
    13167,   # Кагул
    14407,   # Унгень
    12938,   # Сороки
    14027,   # Оргеев
    13359,   # Комрат
    14186,   # Единец
}

# Скорочення для slug (щоб не дублювати)
SLUG_MAP = {
    "Кишинёв": "chisinau",
    "Бельцы": "balti",
    "Бендеры": "bender",
    "Тирасполь": "tiraspol",
    "Кагул": "cahul",
    "Унгень": "ungheni",
    "Сороки": "soroca",
    "Оргеев": "orhei",
    "Комрат": "comrat",
    "Единец": "edinet",
}


def transliterate_ru(text: str) -> str:
    """Транслітерація російської → латиниця."""
    if not text:
        return ""
    mapping = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sh",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    s = text.lower()
    result = "".join(mapping.get(c, c) for c in s)
    result = re.sub(r"[^a-z0-9]+", "-", result)
    return result.strip("-")


def make_slug(name: str, city_id: int, used: set[str]) -> str:
    """Унікальний slug."""
    # Спочатку — з мапи відомих міст
    if name in SLUG_MAP:
        slug = SLUG_MAP[name]
    else:
        slug = transliterate_ru(name)
        if not slug:
            slug = f"loc-{city_id}"

    original = slug
    counter = 1
    while slug in used:
        slug = f"{original}-{counter}"
        counter += 1
    used.add(slug)
    return slug


def main() -> None:
    src = Path("data/raw/md_999md_cities_from_ads.json")
    if not src.exists():
        print(f"❌ {src} не знайдено")
        return

    raw = json.loads(src.read_text(encoding="utf-8"))
    print(f"✅ Міст у джерелі: {len(raw)}")

    cities: list[dict] = []
    used_slugs: set[str] = set()

    for c in raw:
        city_id = c["id"]
        name = c["name"]
        region = c.get("region_name") or ""

        slug = make_slug(name, city_id, used_slugs)

        aliases = [name.lower()]
        # Додати латиницю (з трансліту)
        if transliterate_ru(name):
            aliases.append(transliterate_ru(name))

        cities.append({
            "slug": slug,
            "name": name,           # залишаємо російською (як у 999.md)
            "region": region,
            "priority": city_id in PRIORITY_IDS,
            "refs": {"999md": city_id},
            "aliases": aliases,
        })

    # Сортуємо: спочатку priority, потім за назвою
    cities.sort(key=lambda c: (not c["priority"], c["name"]))

    out = {
        "country": "md",
        "cities": cities,
    }

    out_path = Path("data/cities/md.json")
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n💾 Збережено: {out_path}")
    print(f"Всього міст: {len(cities)}")
    print(f"Priority: {sum(1 for c in cities if c['priority'])}")

    print("\nТоп-15 міст:")
    for c in cities[:15]:
        print(f"  {c['slug']:<20} | {c['name']:<22} | refs={c['refs']['999md']} | {'⭐' if c['priority'] else '  '}")


if __name__ == "__main__":
    main()
