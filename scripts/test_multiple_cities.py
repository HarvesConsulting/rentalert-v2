"""Тест декількох чеських міст."""

from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)
    parser = PARSER_REGISTRY["bezrealitky"]

    cities = ["praha", "brno", "ostrava", "plzen", "liberec", "olomouc"]
    for slug in cities:
        city = catalog.city(slug)
        if not city:
            print(f"❌ {slug}: не знайдено")
            continue
        try:
            listings = parser.fetch(city, ["apartment"])
            print(f"✅ {city.name:20} ({city.refs.get('bezrealitky')}): {len(listings)} оголошень")
        except Exception as e:
            print(f"❌ {city.name}: {e}")


if __name__ == "__main__":
    main()
