"""Тести для SpotahomeParser (JSON-API)."""

from __future__ import annotations

from rentalert.catalog.models import Source
from rentalert.parsers.spotahome import SpotahomeParser


def make_source() -> Source:
    return Source(
        key="spotahome",
        country="es",
        name="Spotahome",
        icon="🏠",
        kind="spotahome",
        base_url="https://www.spotahome.com",
        enabled_by_default=True,
        categories=("apartment", "house", "room"),
        config={},
    )


def make_parser() -> SpotahomeParser:
    return SpotahomeParser(make_source())


# ─────────────────────────────────────────────────────────────
# _parse_one
# ─────────────────────────────────────────────────────────────

def test_parse_one_basic() -> None:
    parser = make_parser()
    raw = {
        "id": 118242,
        "type": "room_shared",
        "title": "Room in shared flat",
        "pricePerMonth": 940,
        "currencySymbol": "€",
        "url": "/barcelona/for-rent:rooms/118242",
        "mainPhotoUrl": "https://photos.spotahome.com/x.jpg",
        "city": "barcelona",
        "area": 85,
        "numberOfBedrooms": 3,
        "location": {"city": "Barcelona", "street": "Carrer X"},
    }
    lst = parser._parse_one(raw, "barcelona")

    assert lst is not None
    assert lst.id == "spotahome:118242"
    assert lst.category == "room"
    assert lst.price == "940 €"
    assert lst.area_m2 == 85.0
    assert lst.rooms == "3"
    assert lst.location == "Barcelona, Carrer X"
    assert lst.link == "https://www.spotahome.com/barcelona/for-rent:rooms/118242"
    assert lst.photo == "https://photos.spotahome.com/x.jpg"


def test_parse_one_missing_id() -> None:
    parser = make_parser()
    assert parser._parse_one({}, "madrid") is None


def test_parse_one_no_price() -> None:
    parser = make_parser()
    raw = {"id": 1, "type": "apartment", "currencySymbol": "€"}
    lst = parser._parse_one(raw, "madrid")
    assert lst is not None
    assert lst.price == "—"


# ─────────────────────────────────────────────────────────────
# _city_aliases
# ─────────────────────────────────────────────────────────────

def test_city_aliases_basic() -> None:
    assert "madrid" in SpotahomeParser._city_aliases("madrid")


def test_city_aliases_diacritics() -> None:
    aliases = SpotahomeParser._city_aliases("malaga")
    assert "malaga" in aliases
    assert "málaga" in aliases


def test_city_aliases_synonyms() -> None:
    assert "lisboa" in SpotahomeParser._city_aliases("lisbon")
    assert "milano" in SpotahomeParser._city_aliases("milan")


# ─────────────────────────────────────────────────────────────
# Category mapping
# ─────────────────────────────────────────────────────────────

def test_category_mapping() -> None:
    parser = make_parser()
    cases = {
        "apartment": "apartment",
        "studio": "apartment",
        "flat": "apartment",
        "house": "house",
        "villa": "house",
        "room_shared": "room",
        "room": "room",
        "residence": "apartment",
    }
    for type_in, cat_out in cases.items():
        raw = {"id": 1, "type": type_in, "currencySymbol": "€"}
        lst = parser._parse_one(raw, "madrid")
        assert lst is not None
        assert lst.category == cat_out, f"type {type_in} → {lst.category}, want {cat_out}"


# ─────────────────────────────────────────────────────────────
# make_id / filter_categories (базові)
# ─────────────────────────────────────────────────────────────

def test_make_id() -> None:
    parser = make_parser()
    assert parser.make_id("118242") == "spotahome:118242"


def test_filter_categories() -> None:
    parser = make_parser()
    assert parser.filter_categories(["apartment", "daily"]) == ["apartment"]
