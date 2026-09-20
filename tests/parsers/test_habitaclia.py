"""Тести для HabitacliaParser на реальній HTML-фікстурі."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rentalert.catalog.models import City, Source
from rentalert.parsers.habitaclia import HabitacliaParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ─────────────────────────────────────────────────────────────
# Спільні фікстури
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def hab_source() -> Source:
    return Source(
        key="habitaclia",
        country="es",
        name="Habitaclia",
        icon="🇪🇸",
        kind="habitaclia",
        base_url="https://www.habitaclia.com",
        enabled_by_default=True,
        categories=("apartment", "house", "room"),
        config={},
    )


@pytest.fixture
def madrid() -> City:
    return City(
        slug="madrid",
        country="es",
        name="Madrid",
        region="",
        priority=True,
        refs={"habitaclia": "madrid"},
    )


@pytest.fixture
def html_fixture() -> str:
    with open(FIXTURES / "habitaclia_page.html", encoding="utf-8") as f:
        return f.read()


# ─────────────────────────────────────────────────────────────
# Тести
# ─────────────────────────────────────────────────────────────


def test_habitaclia_parser_basic(
    hab_source: Source,
    madrid: City,
    html_fixture: str,
    mocker,
) -> None:
    """Парсер повертає оголошення з HTML."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html_fixture

    mocker.patch(
        "rentalert.parsers.habitaclia.cffi_requests.get",
        return_value=mock_response,
    )

    parser = HabitacliaParser(hab_source)
    # Запитуємо всі категорії
    listings = parser.fetch(madrid, ["apartment", "house", "room"])

    assert len(listings) > 0

    first = listings[0]
    assert first.id.startswith("habitaclia:")
    assert first.source_key == "habitaclia"
    assert first.city_slug == "madrid"
    assert first.category in {"apartment", "house", "room"}

    assert first.title
    assert first.link.startswith("https://www.habitaclia.com")


def test_habitaclia_parser_category_filter(
    hab_source: Source,
    madrid: City,
    html_fixture: str,
    mocker,
) -> None:
    """Фільтр категорій пропускає не-квартири, якщо запрошено лише apartment."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html_fixture

    mocker.patch(
        "rentalert.parsers.habitaclia.cffi_requests.get",
        return_value=mock_response,
    )

    parser = HabitacliaParser(hab_source)
    listings = parser.fetch(madrid, ["apartment"])

    # Усі повернені — apartment
    for lst in listings:
        assert lst.category == "apartment"


def test_habitaclia_parser_empty_html(
    hab_source: Source,
    madrid: City,
    mocker,
) -> None:
    """HTML без <article> → порожній список."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>Nothing</p></body></html>"

    mocker.patch(
        "rentalert.parsers.habitaclia.cffi_requests.get",
        return_value=mock_response,
    )

    parser = HabitacliaParser(hab_source)
    listings = parser.fetch(madrid, ["apartment"])

    assert listings == []
