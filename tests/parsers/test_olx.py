"""Тести для OLXParser на реальній фікстурі."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rentalert.catalog.models import City, Source
from rentalert.parsers.olx import OLXParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ─────────────────────────────────────────────────────────────
# Спільні фікстури
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def olx_source() -> Source:
    """Source для olx_ua."""
    return Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="🟢",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment", "house", "room", "daily"),
        config={
            "category_ids": {
                "apartment": 1760,
                "house": 330,
                "room": 1756,
                "daily": 3709,
            }
        },
    )


@pytest.fixture
def kyiv() -> City:
    """Місто Київ."""
    return City(
        slug="kyiv",
        country="ua",
        name="Київ",
        region="Київська область",
        priority=True,
        refs={"olx_ua": 268, "dimria": 10},
    )


@pytest.fixture
def olx_fixture() -> dict:
    """Реальна відповідь OLX API (52 оголошення)."""
    with open(FIXTURES / "olx_ua_response.json", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# Тести
# ─────────────────────────────────────────────────────────────


def test_olx_parser_parses_all_items(
    olx_source: Source,
    kyiv: City,
    olx_fixture: dict,
    mocker,
) -> None:
    """Парсер повертає стільки Listing, скільки item у фікстурі."""
    # Мок Session.get → повертає фікстуру
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = olx_fixture

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    mocker.patch(
        "rentalert.parsers.olx.cffi_requests.Session",
        return_value=mock_session,
    )

    parser = OLXParser(olx_source)
    listings = parser.fetch(kyiv, ["apartment"])

    expected_count = len(olx_fixture["data"])
    assert len(listings) == expected_count
    assert expected_count > 0


def test_olx_parser_listing_fields(
    olx_source: Source,
    kyiv: City,
    olx_fixture: dict,
    mocker,
) -> None:
    """Перший Listing має правильні базові поля."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = olx_fixture

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    mocker.patch(
        "rentalert.parsers.olx.cffi_requests.Session",
        return_value=mock_session,
    )

    parser = OLXParser(olx_source)
    listings = parser.fetch(kyiv, ["apartment"])
    first = listings[0]

    # ID формату source_key:external_id
    assert first.id.startswith("olx_ua:")
    assert first.source_key == "olx_ua"
    assert first.city_slug == "kyiv"
    assert first.category == "apartment"
    assert first.category_icon == "🏢"
    assert first.category_label == "Квартири"

    # Поля з фікстури
    assert first.title  # непорожній
    assert first.link.startswith("https://www.olx.ua")
    assert first.price  # непорожній

    # raw містить оригінал
    assert "id" in first.raw


def test_olx_parser_empty_response(
    olx_source: Source,
    kyiv: City,
    mocker,
) -> None:
    """Порожня відповідь → порожній список."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    mocker.patch(
        "rentalert.parsers.olx.cffi_requests.Session",
        return_value=mock_session,
    )

    parser = OLXParser(olx_source)
    listings = parser.fetch(kyiv, ["apartment"])

    assert listings == []


def test_olx_parser_http_error(
    olx_source: Source,
    kyiv: City,
    mocker,
) -> None:
    """HTTP 500 → порожній список."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    mocker.patch(
        "rentalert.parsers.olx.cffi_requests.Session",
        return_value=mock_session,
    )

    parser = OLXParser(olx_source)
    listings = parser.fetch(kyiv, ["apartment"])

    assert listings == []

def test_olx_parser_pt_skips_sale() -> None:
    """Для Португалії оголошення 'venda' (продаж) не парсяться."""
    from rentalert.catalog.models import City, Source
    from rentalert.parsers.olx import OLXParser

    source = Source(
        key="olx_pt",
        country="pt",
        name="OLX.pt",
        icon="🟢",
        kind="olx",
        base_url="https://www.olx.pt",
        enabled_by_default=True,
        categories=("apartment",),
        config={"category_ids": {"apartment": 16}},
    )
    parser = OLXParser(source)
    city = City(
        slug="porto",
        country="pt",
        name="Porto",
        region="",
        priority=False,
        refs={"olx_pt": 11},
    )

    sale_item = {
        "id": 111,
        "title": "Apartamento T2 para venda",
        "url": "/d/anuncio/111",
        "params": [],
        "location": {},
        "photos": [],
    }
    rent_item = {
        "id": 222,
        "title": "Apartamento T2 para arrendamento",
        "url": "/d/anuncio/222",
        "params": [],
        "location": {},
        "photos": [],
    }

    parsed_sale = parser._parse_item(
        item=sale_item, city_slug="porto", category_key="apartment"
    )
    parsed_rent = parser._parse_item(
        item=rent_item, city_slug="porto", category_key="apartment"
    )

    assert parsed_sale is None  # продаж — пропущено
    assert parsed_rent is not None  # оренда — ок
    assert parsed_rent.id == "olx_pt:222"


def test_olx_parser_ua_keeps_sale() -> None:
    """Для України фільтр 'venda' НЕ застосовується (це PT-специфіка)."""
    from rentalert.catalog.models import Source
    from rentalert.parsers.olx import OLXParser

    source = Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="🟢",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment",),
        config={"category_ids": {"apartment": 1760}},
    )
    parser = OLXParser(source)

    # Оголошення з "venda" в заголовку — має пройти (бо це ua)
    item = {
        "id": 333,
        "title": "Квартира для venda (тест)",
        "url": "/d/anuncio/333",
        "params": [],
        "location": {},
        "photos": [],
    }

    parsed = parser._parse_item(
        item=item, city_slug="kyiv", category_key="apartment"
    )

    # Для ua фільтр не застосовується — оголошення проходить
    assert parsed is not None
