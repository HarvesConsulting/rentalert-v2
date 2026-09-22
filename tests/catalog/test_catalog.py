"""Тести для Catalog — класу довідника.

Використовують реальні data/ (не моки) — щоб переконатись,
що каталог дійсно завантажується і працює.
"""

from pathlib import Path

import pytest

from rentalert.catalog.catalog import Catalog

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    """Завантажений каталог — один раз на всі тести."""
    return Catalog.load(DATA_DIR)


# ─── Базові властивості ───


def test_stats(catalog: Catalog) -> None:
    s = catalog.stats()
    assert s["countries"] == 9
    assert s["sources"] == 10
    assert s["cities"] > 34414


def test_all_countries(catalog: Catalog) -> None:
    codes = {c.code for c in catalog.all_countries()}
    assert codes == {"ua", "pl", "pt", "ro", "bg", "de", "es", "hr", "fr"}


def test_all_sources(catalog: Catalog) -> None:
    keys = {s.key for s in catalog.all_sources()}
    assert "olx_ua" in keys


# ─── Прямий доступ ───


def test_country_lookup(catalog: Catalog) -> None:
    ua = catalog.country("ua")
    assert ua is not None
    assert ua.code == "ua"
    assert ua.currency == "грн"
    assert ua.free is True


def test_country_not_found(catalog: Catalog) -> None:
    assert catalog.country("xx") is None


def test_source_lookup(catalog: Catalog) -> None:
    olx = catalog.source("olx_ua")
    assert olx is not None
    assert olx.key == "olx_ua"
    assert olx.kind == "olx"
    assert "apartment" in olx.categories


def test_city_lookup(catalog: Catalog) -> None:
    kyiv = catalog.city("kyiv")
    assert kyiv is not None
    assert kyiv.name == "Київ"
    assert kyiv.country == "ua"
    assert kyiv.priority is True
    assert kyiv.refs == {"olx_ua": 268, "dimria": 10}


def test_city_not_found(catalog: Catalog) -> None:
    assert catalog.city("nonexistent_city") is None


# ─── Колекції ───


def test_cities_of_ua(catalog: Catalog) -> None:
    cities = catalog.cities_of("ua")
    assert len(cities) > 20000
    assert all(c.country == "ua" for c in cities)


def test_sources_of_ua(catalog: Catalog) -> None:
    sources = catalog.sources_of("ua")
    keys = {s.key for s in sources}
    assert keys == {"olx_ua", "dimria"}


# ─── Зворотний пошук ───


def test_find_city_by_external_id(catalog: Catalog) -> None:
    kyiv = catalog.find_city_by_external_id("olx_ua", 268)
    assert kyiv is not None
    assert kyiv.slug == "kyiv"


def test_find_city_by_external_id_not_found(catalog: Catalog) -> None:
    assert catalog.find_city_by_external_id("olx_ua", 999999999) is None


def test_find_city_by_external_id_wrong_source(catalog: Catalog) -> None:
    assert catalog.find_city_by_external_id("olx_pl", 268) is None


# ─── Пошук міст ───


def test_find_cities_exact(catalog: Catalog) -> None:
    results = catalog.find_cities("Київ", "ua", limit=5)
    assert len(results) > 0
    assert results[0].slug == "kyiv"
    assert results[0].priority is True


def test_find_cities_priority_first(catalog: Catalog) -> None:
    results = catalog.find_cities("ки", "ua", limit=5)
    assert results[0].slug == "kyiv"
    assert results[0].priority is True


def test_find_cities_limit(catalog: Catalog) -> None:
    results = catalog.find_cities("ки", "ua", limit=3)
    assert len(results) <= 3


def test_find_cities_short_query(catalog: Catalog) -> None:
    assert catalog.find_cities("к", "ua") == []
    assert catalog.find_cities("", "ua") == []


def test_find_cities_not_found(catalog: Catalog) -> None:
    assert catalog.find_cities("zzzzzz", "ua") == []


def test_find_cities_diacritics(catalog: Catalog) -> None:
    lower = catalog.find_cities("warszawa", "pl", limit=3)
    upper = catalog.find_cities("WARSZAWA", "pl", limit=3)
    assert len(lower) > 0
    assert len(upper) > 0
    assert lower[0].slug == upper[0].slug == "warszawa"


# ─── Джерела для міста ───


def test_sources_for_city_kyiv(catalog: Catalog) -> None:
    sources = catalog.sources_for_city("kyiv")
    keys = {s.key for s in sources}
    assert keys == {"olx_ua", "dimria"}


def test_sources_for_city_warszawa(catalog: Catalog) -> None:
    sources = catalog.sources_for_city("warszawa")
    keys = {s.key for s in sources}
    assert keys == {"olx_pl"}


def test_sources_for_city_not_found(catalog: Catalog) -> None:
    assert catalog.sources_for_city("nonexistent") == []


# ─── City helper methods ───


def test_city_external_id(catalog: Catalog) -> None:
    kyiv = catalog.city("kyiv")
    assert kyiv is not None
    assert kyiv.external_id("olx_ua") == 268
    assert kyiv.external_id("dimria") == 10
    assert kyiv.external_id("olx_pl") is None


def test_city_supports(catalog: Catalog) -> None:
    kyiv = catalog.city("kyiv")
    assert kyiv is not None
    assert kyiv.supports("olx_ua") is True
    assert kyiv.supports("dimria") is True
    assert kyiv.supports("olx_pl") is False


def test_city_source_keys(catalog: Catalog) -> None:
    kyiv = catalog.city("kyiv")
    assert kyiv is not None
    keys = set(kyiv.source_keys())
    assert keys == {"olx_ua", "dimria"}
