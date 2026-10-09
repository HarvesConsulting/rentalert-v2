"""Тести для SpotahomeParser на реалістичній JSON-фікстурі."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rentalert.catalog.models import Source
from rentalert.parsers.spotahome import SpotahomeParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def spotahome_source() -> Source:
    return Source(
        key="spotahome", country="es", name="Spotahome", icon="🏠",
        kind="spotahome", base_url="https://www.spotahome.com",
        enabled_by_default=True, categories=("apartment", "house", "room"),
        config={},
    )


@pytest.fixture
def homecards_data() -> dict:
    with open(FIXTURES / "spotahome_homecards.json", encoding="utf-8-sig") as f:
        return json.load(f)


@pytest.fixture
def parser(spotahome_source: Source) -> SpotahomeParser:
    return SpotahomeParser(spotahome_source)


def test_parse_homecards_basic(parser, homecards_data) -> None:
    listings = parser._parse_homecards(homecards_data, "barcelona")
    assert len(listings) == 2
    assert listings[0].id.startswith("spotahome:")


def test_parse_homecards_fields(parser, homecards_data) -> None:
    first = parser._parse_homecards(homecards_data, "barcelona")[0]
    assert first.id == "spotahome:118242"
    assert first.price == "940 €"
    assert first.category == "room"
    assert first.area_m2 == 85.0


def test_parse_homecards_empty(parser) -> None:
    assert parser._parse_homecards({}, "barcelona") == []


@pytest.mark.parametrize(
    ("type_in", "cat_out"),
    [("apartment", "apartment"), ("studio", "apartment"),
     ("house", "house"), ("villa", "house"),
     ("room_shared", "room"), ("room", "room")],
)
def test_category_mapping(parser, type_in, cat_out) -> None:
    data = {"currency": "EUR", "homecards": [{"id": "1", "type": type_in}]}
    assert parser._parse_homecards(data, "madrid")[0].category == cat_out


@pytest.mark.parametrize(
    ("inp", "cur", "out"),
    [("940", "EUR", "940 €"), ("1234.56", "EUR", "1234.56 €"),
     ("500", "USD", "500 $"), ("500", "PLN", "500 zł")],
)
def test_format_price(inp, cur, out) -> None:
    assert SpotahomeParser._format_price(inp, cur) == out


def test_make_id(parser) -> None:
    assert parser.make_id("118242") == "spotahome:118242"


def test_filter_categories(parser) -> None:
    assert parser.filter_categories(["apartment", "daily"]) == ["apartment"]
