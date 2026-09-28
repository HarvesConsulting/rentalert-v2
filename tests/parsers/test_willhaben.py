"""Тести для WillhabenParser."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from rentalert.catalog.models import City, Source
from rentalert.parsers.willhaben import WillhabenParser


@pytest.fixture
def source() -> Source:
    return Source(
        key="willhaben",
        country="at",
        name="Willhaben",
        icon="🇦🇹",
        kind="willhaben",
        base_url="https://www.willhaben.at",
        enabled_by_default=True,
        categories=("apartment", "house"),
        config={
            "category_urls": {
                "apartment": "iad/immobilien/mietwohnungen",
                "house": "iad/immobilien/haus-mieten",
            }
        },
    )


@pytest.fixture
def city() -> City:
    return City(
        slug="wien",
        country="at",
        name="Wien",
        region="Wien",
        priority=True,
        refs={"willhaben": "wien"},
    )


@pytest.fixture
def parser(source: Source) -> WillhabenParser:
    return WillhabenParser(source)


def _make_next_data(items: list[dict]) -> str:
    """Формує HTML з __NEXT_DATA__ для тесту."""
    data = {
        "props": {"pageProps": {"searchResult": {"advertSummaryList": {"advertSummary": items}}}}
    }
    return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'


def _sample_item(
    item_id: str = "1980123758",
    title: str = "Einzigartige Wohnung 150 m²",
    price: str = "€ 1.550",
    ad_type_id: int = 2,
) -> dict:
    """Приклад advertSummary."""
    return {
        "id": item_id,
        "adTypeId": ad_type_id,
        "description": title,
        "attributes": {
            "attribute": [
                {"name": "HEADING", "values": [title]},
                {"name": "PRICE_FOR_DISPLAY", "values": [price]},
                {"name": "PRICE", "values": ["1550"]},
                {"name": "LOCATION", "values": ["Pettenbach"]},
                {"name": "POSTCODE", "values": ["4643"]},
                {"name": "DISTRICT", "values": ["Kirchdorf an der Krems"]},
                {"name": "NUMBER_OF_ROOMS", "values": ["5"]},
                {
                    "name": "SEO_URL",
                    "values": ["immobilien/d/.../einzigartige-wohnung-150-m-1980123758/"],
                },
                {"name": "PUBLISHED_String", "values": ["2026-09-27T17:20:32Z"]},
            ]
        },
        "advertImageList": {
            "advertImage": [{"mainImageUrl": "https://cache.willhaben.at/mmo/test.jpg"}]
        },
    }


# ─── Тести ───


def test_extract_items_empty(parser: WillhabenParser) -> None:
    """Порожній HTML → порожній список."""
    assert parser._extract_items("<html></html>") == []


def test_extract_items_from_next_data(parser: WillhabenParser) -> None:
    """Витягує items з __NEXT_DATA__."""
    item = _sample_item()
    html = _make_next_data([item])

    items = parser._extract_items(html)
    assert len(items) == 1
    assert items[0]["id"] == "1980123758"


def test_parse_item_basic(parser: WillhabenParser) -> None:
    """Парсить один item."""
    item = _sample_item()
    listing = parser._parse_item(
        item=item,
        city_slug="wien",
        category_key="apartment",
    )

    assert listing is not None
    assert listing.id == "willhaben:1980123758"
    assert listing.title == "Einzigartige Wohnung 150 m²"
    assert listing.price == "€ 1.550"
    assert listing.rooms == "5"
    assert listing.category == "apartment"
    assert listing.city_slug == "wien"


def test_parse_item_skips_sale(parser: WillhabenParser) -> None:
    """Пропускає продаж (adTypeId != 2)."""
    item = _sample_item(ad_type_id=1)  # 1 = продаж
    listing = parser._parse_item(
        item=item,
        city_slug="wien",
        category_key="apartment",
    )

    assert listing is None


def test_parse_item_no_id(parser: WillhabenParser) -> None:
    """Без ID → None."""
    item = _sample_item()
    item["id"] = None

    listing = parser._parse_item(
        item=item,
        city_slug="wien",
        category_key="apartment",
    )
    assert listing is None


def test_fetch_calls_api(parser: WillhabenParser, city: City, mocker) -> None:
    """fetch() викликає HTTP і повертає listings."""
    item = _sample_item()
    html = _make_next_data([item])

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    mocker.patch(
        "rentalert.parsers.willhaben.fetch_with_retry",
        return_value=mock_response,
    )
    mocker.patch("rentalert.parsers.willhaben.human_delay")

    listings = parser.fetch(city, ["apartment"])

    assert len(listings) == 1
    assert listings[0].id == "willhaben:1980123758"
