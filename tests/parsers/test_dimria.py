"""Тести для DimriaParser на реальних фікстурах."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rentalert.catalog.models import City, Source
from rentalert.parsers.dimria import DimriaParser

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ─────────────────────────────────────────────────────────────
# Спільні фікстури
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def dimria_source() -> Source:
    return Source(
        key="dimria",
        country="ua",
        name="DIM.RIA",
        icon="🏘",
        kind="dimria",
        base_url="https://dom.ria.com",
        enabled_by_default=False,
        categories=("apartment", "house"),
        config={},
    )


@pytest.fixture
def kyiv() -> City:
    return City(
        slug="kyiv",
        country="ua",
        name="Київ",
        region="Київська область",
        priority=True,
        refs={"olx_ua": 268, "dimria": 10},
    )


@pytest.fixture
def dimria_search() -> dict:
    with open(FIXTURES / "dimria_search_response.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def dimria_info() -> dict:
    with open(FIXTURES / "dimria_info_response.json", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# Тести
# ─────────────────────────────────────────────────────────────


def test_dimria_parser_no_api_key(
    dimria_source: Source,
    kyiv: City,
    monkeypatch,
) -> None:
    """Без API-ключа → порожній список."""
    monkeypatch.delenv("DIMRIA_API_KEY", raising=False)

    parser = DimriaParser(dimria_source)
    # API-ключ читається з config, але у тестах config порожній
    parser.api_key = ""  # примусово

    listings = parser.fetch(kyiv, ["apartment"])
    assert listings == []


def test_dimria_parser_full(
    dimria_source: Source,
    kyiv: City,
    dimria_search: dict,
    dimria_info: dict,
    mocker,
) -> None:
    """Повний парсинг: search + info."""
    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = dimria_search

    info_resp = MagicMock()
    info_resp.status_code = 200
    info_resp.json.return_value = dimria_info

    # cffi_requests.get викликається двічі: search і info
    mocker.patch(
        "rentalert.parsers.dimria.cffi_requests.get",
        side_effect=[search_resp, info_resp],
    )
    # Прибираємо rate limit
    mocker.patch("rentalert.parsers.dimria._wait_for_slot")

    parser = DimriaParser(dimria_source)
    parser.api_key = "test_key"

    listings = parser.fetch(kyiv, ["apartment"])

    assert len(listings) == 1
    first = listings[0]

    # ID формату source_key:realty_id
    assert first.id.startswith("dimria:")
    assert first.source_key == "dimria"
    assert first.city_slug == "kyiv"
    assert first.category == "apartment"
    assert first.category_icon == "🏘"

    # Поля з info
    assert first.title
    assert first.link.startswith("https://dom.ria.com")
    assert first.price


def test_dimria_parser_empty_search(
    dimria_source: Source,
    kyiv: City,
    mocker,
) -> None:
    """Порожній search → порожній список."""
    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.json.return_value = {"count": 0, "items": []}

    mocker.patch(
        "rentalert.parsers.dimria.cffi_requests.get",
        return_value=empty_resp,
    )
    mocker.patch("rentalert.parsers.dimria._wait_for_slot")

    parser = DimriaParser(dimria_source)
    parser.api_key = "test_key"

    listings = parser.fetch(kyiv, ["apartment"])
    assert listings == []
