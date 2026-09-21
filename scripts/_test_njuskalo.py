"""Локальний тест NjuskaloParser (реальний HTTP)."""

from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.njuskalo import NjuskaloParser
from rentalert.parsers.registry import build_registry


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)

    parser = NjuskaloParser(catalog.source("njuskalo"))
    city = catalog.city("zagreb")

    print(f"City: {city.name} ({city.slug})")
    print(f"Refs: {city.refs}")
    print()

    listings = parser.fetch(city, ["apartment"])

    print(f"✅ Отримано {len(listings)} оголошень\n")

    for i, lst in enumerate(listings[:5], 1):
        print(f"#{i}")
        print(f"  ID:       {lst.id}")
        print(f"  Title:    {lst.title[:80]}")
        print(f"  Price:    {lst.price}")
        print(f"  Location: {lst.location}")
        print(f"  Rooms:    {lst.rooms}")
        print(f"  Link:     {lst.link[:80]}")
        print(f"  Photo:    {lst.photo[:80]}")
        print(f"  Created:  {lst.created_at}")
        print()


if __name__ == "__main__":
    main()
