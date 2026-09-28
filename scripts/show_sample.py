"""Показує приклади оголошень для перевірки полів."""

from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import build_registry, PARSER_REGISTRY


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)
    parser = PARSER_REGISTRY["bezrealitky"]

    # Показуємо 5 оголошень з Brno (менше навантаження)
    brno = catalog.city("brno")
    listings = parser.fetch(brno, ["apartment"])

    print(f"=== Brno: {len(listings)} оголошень ===\n")

    for i, lst in enumerate(listings[:5], 1):
        print(f"--- #{i} ---")
        print(f"  id:              {lst.id}")
        print(f"  source_key:      {lst.source_key}")
        print(f"  city_slug:       {lst.city_slug}")
        print(f"  title:           {lst.title!r}")
        print(f"  price:           {lst.price!r}")
        print(f"  location:        {lst.location!r}")
        print(f"  link:            {lst.link}")
        print(f"  photo:           {lst.photo[:80]}..." if lst.photo else "  photo:           —")
        print(f"  rooms:           {lst.rooms!r}")
        print(f"  category:        {lst.category}")
        print(f"  category_icon:   {lst.category_icon}")
        print(f"  category_label:  {lst.category_label}")
        print(f"  created_at:      {lst.created_at}")
        print()


if __name__ == "__main__":
    main()
