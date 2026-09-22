"""Реєстр парсерів: source_key → Parser.

Будується один раз при старті з каталогу.
Використовується агрегатором для отримання парсера за ключем джерела.
"""

from __future__ import annotations

import logging

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.base import Parser

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Мапінг kind → клас парсера
# ─────────────────────────────────────────────────────────────

# Імпорти парсерів зробимо ліниво, щоб уникнути циклічних залежностей
_PARSER_BY_KIND: dict[str, type[Parser]] = {}


def _register_parser_classes() -> None:
    global _PARSER_BY_KIND
    if _PARSER_BY_KIND:
        return

    from rentalert.parsers.bienici import BienIciParser
    from rentalert.parsers.dimria import DimriaParser
    from rentalert.parsers.habitaclia import HabitacliaParser
    from rentalert.parsers.kleinanzeigen import KleinanzeigenParser
    from rentalert.parsers.nekretnine import NekretnineParser
    from rentalert.parsers.olx import OLXParser
    from rentalert.parsers.openrent import OpenRentParser

    _PARSER_BY_KIND = {
        "olx": OLXParser,
        "dimria": DimriaParser,
        "kleinanzeigen": KleinanzeigenParser,
        "habitaclia": HabitacliaParser,
        "nekretnine": NekretnineParser,
        "bienici": BienIciParser,
        "openrent": OpenRentParser,
    }


# ─────────────────────────────────────────────────────────────
# Глобальний реєстр
# ─────────────────────────────────────────────────────────────

PARSER_REGISTRY: dict[str, Parser] = {}


def build_registry(catalog: Catalog) -> dict[str, Parser]:
    """Будує PARSER_REGISTRY з усіх Source у каталозі.

    Приклад:
        catalog = Catalog.load(Path("data"))
        build_registry(catalog)
        parser = PARSER_REGISTRY["olx_ua"]

    Raises:
        ValueError: якщо для якогось Source немає парсера.
    """
    _register_parser_classes()

    PARSER_REGISTRY.clear()

    for source in catalog.all_sources():
        parser_cls = _PARSER_BY_KIND.get(source.kind)
        if parser_cls is None:
            log.warning(
                "Невідомий kind=%r у Source(key=%r), пропускаю",
                source.kind,
                source.key,
            )
            continue

        PARSER_REGISTRY[source.key] = parser_cls(source)
        log.debug("Зареєстровано %s → %s", source.key, parser_cls.__name__)

    log.info("PARSER_REGISTRY: %d парсерів", len(PARSER_REGISTRY))
    return PARSER_REGISTRY


def get_parser(source_key: str) -> Parser | None:
    """Повертає парсер за ключем або None."""
    return PARSER_REGISTRY.get(source_key)


def registered_keys() -> list[str]:
    """Список усіх зареєстрованих ключів."""
    return list(PARSER_REGISTRY.keys())
