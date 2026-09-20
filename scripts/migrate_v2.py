"""Одноразова міграція з v1 на v2. Заповнимо на Етапі 10.

Призначення:
- Перетворити старі city_slug ('olx_121', 'dnipro', 'es_madrid')
  на нові slug ('kyiv', 'dnipro', 'madrid').
- Додати source_key у seen_listings.
- Оновити user_sources: country + source_key → просто source_key.
- Видалити застарілі таблиці user_dimria_cities, dimria_cities.

Запуск:
    python scripts/migrate_v2.py

Скрипт ідемпотентний — можна запускати кілька разів.
"""


def main() -> None:
    print("Міграція v1 → v2 (ще не реалізована)")


if __name__ == "__main__":
    main()
