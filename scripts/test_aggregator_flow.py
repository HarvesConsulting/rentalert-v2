"""Тест інтеграції Bezrealitky з aggregator.py."""

import inspect
from pathlib import Path

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.registry import build_registry, PARSER_REGISTRY


def main() -> None:
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)
    parser = PARSER_REGISTRY["bezrealitky"]

    # 1. Перевірка signature
    sig = inspect.signature(parser.fetch)
    print(f"Signature: {sig}")
    print(f"has seen_checker: {'seen_checker' in sig.parameters}")
    print()

    # 2. Тест з seen_checker=True (імітація "всі в БД")
    calls = [0]

    def always_true(ids: list[str]) -> bool:
        calls[0] += 1
        return True

    brno = catalog.city("brno")
    print(f"🔍 seen_checker=True для {brno.name}...")
    listings = parser.fetch(brno, ["apartment"], seen_checker=always_true)
    print(f"✅ Отримано: {len(listings)} (мало бути 100 — зупинився на 1-й сторінці)")
    print(f"   seen_checker викликано: {calls[0]} раз")
    print()

    # 3. Тест з seen_checker=False (повний цикл)
    def always_false(ids: list[str]) -> bool:
        return False

    print(f"🔍 seen_checker=False для {brno.name}...")
    listings2 = parser.fetch(brno, ["apartment"], seen_checker=always_false)
    print(f"✅ Отримано: {len(listings2)} (мало бути 138 — повний цикл)")


if __name__ == "__main__":
    main()
