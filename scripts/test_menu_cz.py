"""Тест меню бота для Чехії — симуляція клавіатур."""

from pathlib import Path

from rentalert.bot import keyboards as kb
from rentalert.catalog.catalog import Catalog


def main() -> None:
    catalog = Catalog.load(Path("data"))

    # 1. Список країн
    print("=" * 60)
    print("1. Список країн")
    print("=" * 60)
    countries = [
        {
            "code": c.code,
            "name": c.name,
            "free": c.free,
            "price_stars": c.price_stars,
        }
        for c in catalog.all_countries()
    ]
    for c in countries:
        marker = " ← ЧЕХІЯ" if c["code"] == "cz" else ""
        print(f"  {c['code']}: {c['name']}{marker}")

    # 2. Клавіатура країн
    print()
    print("=" * 60)
    print("2. Клавіатура країн (поточна = cz)")
    print("=" * 60)
    keyboard = kb.country_selector_keyboard(countries, current="cz", lang="uk")
    for row in keyboard["inline_keyboard"]:
        for btn in row:
            text = btn["text"]
            cb = btn["callback_data"]
            marker = "  ⭐" if "cz" in cb else ""
            print(f"  {text}  [{cb}]{marker}")

    # 3. Топ-5 чеських міст
    print()
    print("=" * 60)
    print("3. Топ-5 чеських міст (popular_cities_keyboard)")
    print("=" * 60)
    popular = [c for c in catalog.cities_of("cz") if c.priority][:5]
    for c in popular:
        print(f"  • {c.name} ({c.region or '—'})")

    keyboard = kb.popular_cities_keyboard(popular, lang="uk")
    print()
    print("Кнопки:")
    for row in keyboard["inline_keyboard"]:
        for btn in row:
            print(f"  • {btn['text']}  [{btn['callback_data']}]")

    # 4. Чеські категорії
    print()
    print("=" * 60)
    print("4. Чеські категорії (categories_keyboard)")
    print("=" * 60)
    categories = kb._categories_for_country("cz")
    for cat_key, icon, label in categories:
        print(f"  {icon} {label}  [{cat_key}]")


if __name__ == "__main__":
    main()
