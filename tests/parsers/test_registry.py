"""Тести для PARSER_REGISTRY."""

from __future__ import annotations

from pathlib import Path

import pytest

from rentalert.catalog.catalog import Catalog
from rentalert.parsers.dimria import DimriaParser
from rentalert.parsers.habitaclia import HabitacliaParser
from rentalert.parsers.kleinanzeigen import KleinanzeigenParser
from rentalert.parsers.olx import OLXParser
from rentalert.parsers.registry import (
    PARSER_REGISTRY,
    build_registry,
    get_parser,
    registered_keys,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return Catalog.load(DATA_DIR)


@pytest.fixture(scope="module", autouse=True)
def _build(catalog: Catalog):
    """Будує реєстр один раз на всі тести модуля."""
    build_registry(catalog)
    yield


def test_registry_has_all_sources() -> None:
    """Реєстр містить усі 9 джерел з каталогу."""
    keys = registered_keys()
    expected = {
        "olx_ua",
        "dimria",
        "olx_pl",
        "olx_pt",
        "olx_ro",
        "olx_bg",
        "kleinanzeigen",
        "habitaclia",
        "nekretnine",
    }
    assert set(keys) == expected


def test_registry_parser_types() -> None:
    """Правильні класи парсерів для кожного ключа."""
    assert isinstance(PARSER_REGISTRY["olx_ua"], OLXParser)
    assert isinstance(PARSER_REGISTRY["olx_pl"], OLXParser)
    assert isinstance(PARSER_REGISTRY["olx_pt"], OLXParser)
    assert isinstance(PARSER_REGISTRY["olx_ro"], OLXParser)
    assert isinstance(PARSER_REGISTRY["olx_bg"], OLXParser)
    assert isinstance(PARSER_REGISTRY["dimria"], DimriaParser)
    assert isinstance(PARSER_REGISTRY["kleinanzeigen"], KleinanzeigenParser)
    assert isinstance(PARSER_REGISTRY["habitaclia"], HabitacliaParser)
    from rentalert.parsers.nekretnine import NekretnineParser

    assert isinstance(PARSER_REGISTRY["nekretnine"], NekretnineParser)


def test_get_parser_unknown() -> None:
    """Невідомий ключ → None."""
    assert get_parser("nonexistent") is None
    assert get_parser("olx_ua") is not None
