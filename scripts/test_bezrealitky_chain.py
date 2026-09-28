"""Фінальний тест GraphQL-парсера."""

from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import build_registry, PARSER_REGISTRY


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)

    parser = PARSER_REGISTRY["bezrealitky"]
    praha = catalog.city("praha")

    print(f"🔍 Тестуємо {praha.name} (OSM: R{praha.refs.get('bezrealitky')})\n")

    listings = parser.fetch(praha, ["apartment"])
    print(f"✅ Отримано {len(listings)} оголошень\n")

    for i, lst in enumerate(listings[:5], 1):
        print(f"--- #{i} ---")
        print(f"  ID:       {lst.id}")
        print(f"  Title:    {lst.title}")
        print(f"  Price:    {lst.price}")
        print(f"  Location: {lst.location}")
        print(f"  Rooms:    {lst.rooms}")
        print(f"  Photo:    {lst.photo[:80]}..." if lst.photo else "  Photo:    —")
        print(f"  Link:     {lst.link}")
        print()


if __name__ == "__main__":
    main()
