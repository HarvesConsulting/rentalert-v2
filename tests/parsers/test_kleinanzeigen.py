"""Тести для KleinanzeigenParser на реальній HTML-фікстурі."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rentalert.catalog.models import City, Source
from rentalert.parsers.kleinanzeigen import KleinanzeigenParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ─────────────────────────────────────────────────────────────
# Спільні фікстури
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def kz_source() -> Source:
    return Source(
        key="kleinanzeigen",
        country="de",
        name="Kleinanzeigen",
        icon="🇩🇪",
        kind="kleinanzeigen",
        base_url="https://www.kleinanzeigen.de",
        enabled_by_default=True,
        categories=("apartment", "house", "room"),
        config={
            "category_slugs": {
                "apartment": "wohnung-mieten",
                "house": "haus-mieten",
                "room": "wg-zimmer",
            }
        },
    )


@pytest.fixture
def berlin() -> City:
    return City(
        slug="berlin",
        country="de",
        name="Berlin",
        region="Berlin",
        priority=True,
        refs={"kleinanzeigen": "3331"},
    )


@pytest.fixture
def html_fixture() -> str:
    with open(FIXTURES / "kleinanzeigen_page.html", encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────
# Тести
# ─────────────────────────────────────────────────────────────


def test_kleinanzeigen_parser_basic(
    kz_source: Source,
    berlin: City,
    html_fixture: str,
    mocker,
) -> None:
    """Парсер повертає оголошення з HTML."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html_fixture

    mocker.patch(
        "rentalert.parsers.kleinanzeigen.cffi_requests.get",
        return_value=mock_response,
    )

    parser = KleinanzeigenParser(kz_source)
    listings = parser.fetch(berlin, ["apartment"])

    assert len(listings) > 0

    first = listings[0]
    assert first.id.startswith("kleinanzeigen:")
    assert first.source_key == "kleinanzeigen"
    assert first.city_slug == "berlin"
    assert first.category == "apartment"
    assert first.category_icon == "🏢"
    assert first.category_label == "Wohnungen"

    assert first.title
    assert first.link.startswith("https://www.kleinanzeigen.de")


def test_kleinanzeigen_parser_empty_html(
    kz_source: Source,
    berlin: City,
    mocker,
) -> None:
    """HTML без <article> → порожній список."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>Nothing here</p></body></html>"

    mocker.patch(
        "rentalert.parsers.kleinanzeigen.cffi_requests.get",
        return_value=mock_response,
    )

    parser = KleinanzeigenParser(kz_source)
    listings = parser.fetch(berlin, ["apartment"])

    assert listings == []


def test_kleinanzeigen_parser_http_error(
    kz_source: Source,
    berlin: City,
    mocker,
) -> None:
    """HTTP 404 → порожній список."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    mocker.patch(
        "rentalert.parsers.kleinanzeigen.cffi_requests.get",
        return_value=mock_response,
    )

    parser = KleinanzeigenParser(kz_source)
    listings = parser.fetch(berlin, ["apartment"])

    assert listings == []
