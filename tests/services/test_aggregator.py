"""Тести для aggregator.py.

Мокаємо catalog, client, notify_fn.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from rentalert.catalog.models import City, Source
from rentalert.parsers.base import Listing
from rentalert.services.aggregator import (
    run_aggregation_cycle,
)

# ─────────────────────────────────────────────────────────────
# Спільні фікстури
# ─────────────────────────────────────────────────────────────


@pytest.fixture
def kyiv() -> City:
    return City(
        slug="kyiv",
        country="ua",
        name="Київ",
        region="Київська область",
        priority=True,
        refs={"olx_ua": 268},
    )


@pytest.fixture
def catalog(kyiv: City) -> MagicMock:
    cat = MagicMock()
    cat.city.side_effect = lambda slug: kyiv if slug == "kyiv" else None
    return cat


@pytest.fixture
def listing() -> Listing:
    return Listing(
        id="olx_ua:12345",
        source_key="olx_ua",
        city_slug="kyiv",
        title="Test listing",
        price="1000",
        location="Kyiv",
        link="https://olx.ua/123",
        photo="",
        rooms="2",
        category="apartment",
        category_icon="🏢",
        category_label="Квартири",
        created_at=datetime.now(UTC),
    )


# ─────────────────────────────────────────────────────────────
# Тести
# ─────────────────────────────────────────────────────────────


def test_cycle_no_subscriptions(catalog, mocker) -> None:
    """Немає підписок → порожня статистика."""
    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_cities",
        return_value={},
    )
    client = MagicMock()
    notify = MagicMock()

    stats = run_aggregation_cycle(catalog, client, notify)

    assert stats.pairs_checked == 0
    assert stats.listings_new == 0
    notify.assert_not_called()


def test_cycle_new_listing(catalog, listing, mocker) -> None:
    """Знайдено нове оголошення → розсилка."""
    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_cities",
        return_value={"123": ["kyiv"]},
    )
    mocker.patch(
    "rentalert.services.aggregator.db.get_distinct_city_slugs",
    return_value=["kyiv"],
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_seen_ids",
        return_value=set(),
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_disabled_sources",
        return_value=set(),
    )
    mock_save = mocker.patch("rentalert.services.aggregator.db.save_listing")

    # Мокаємо парсер
    mock_parser = MagicMock()
    mock_parser.source = Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="X",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment",),
        config={},
    )
    mock_parser.fetch.return_value = [listing]

    mocker.patch(
        "rentalert.services.aggregator.PARSER_REGISTRY",
        {"olx_ua": mock_parser},
    )

    client = MagicMock()
    notify = MagicMock()

    stats = run_aggregation_cycle(catalog, client, notify)

    assert stats.pairs_checked == 1
    assert stats.listings_fetched == 1
    assert stats.listings_new == 1
    assert stats.users_notified == 1
    assert stats.errors == 0
    mock_save.assert_called_once()
    notify.assert_called_once_with("123", "kyiv", [listing])


def test_cycle_seen_listing(catalog, listing, mocker) -> None:
    """Оголошення вже бачили → не розсилаємо."""
    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_cities",
        return_value={"123": ["kyiv"]},
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_seen_ids",
        return_value={"olx_ua:12345"},
    )
    mocker.patch("rentalert.services.aggregator.db.get_disabled_sources", return_value=set())
    mocker.patch("rentalert.services.aggregator.db.save_listing")

    mock_parser = MagicMock()
    mock_parser.source = Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="X",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment",),
        config={},
    )
    mock_parser.fetch.return_value = [listing]

    mocker.patch("rentalert.services.aggregator.PARSER_REGISTRY", {"olx_ua": mock_parser})

    client = MagicMock()
    notify = MagicMock()

    stats = run_aggregation_cycle(catalog, client, notify)

    assert stats.listings_new == 0
    assert stats.users_notified == 0
    notify.assert_not_called()


def test_cycle_disabled_source(catalog, listing, mocker) -> None:
    """Користувач вимкнув джерело → не отримує."""
    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_cities",
        return_value={"123": ["kyiv"]},
    )
    mocker.patch(
    "rentalert.services.aggregator.db.get_distinct_city_slugs",
    return_value=["kyiv"],
    )
    mocker.patch("rentalert.services.aggregator.db.get_seen_ids", return_value=set())
    mocker.patch(
        "rentalert.services.aggregator.db.get_disabled_sources",
        return_value={"olx_ua"},
    )
    mocker.patch("rentalert.services.aggregator.db.save_listing")

    mock_parser = MagicMock()
    mock_parser.source = Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="X",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment",),
        config={},
    )
    mock_parser.fetch.return_value = [listing]

    mocker.patch("rentalert.services.aggregator.PARSER_REGISTRY", {"olx_ua": mock_parser})

    client = MagicMock()
    notify = MagicMock()

    stats = run_aggregation_cycle(catalog, client, notify)

    assert stats.listings_new == 1  # зберігаємо в БД
    assert stats.users_notified == 0  # але не розсилаємо
    notify.assert_not_called()

def test_cycle_respects_enabled_categories(catalog, listing, mocker) -> None:
    """Користувач увімкнув тільки 'apartment' → отримує лише квартири."""
    # Друге оголошення — кімната
    room_listing = Listing(
        id="olx_ua:99999",
        source_key="olx_ua",
        city_slug="kyiv",
        title="Room listing",
        price="500",
        location="Kyiv",
        link="https://olx.ua/999",
        photo="",
        rooms="1",
        category="room",
        category_icon="🚪",
        category_label="Кімнати",
        created_at=datetime.now(UTC),
    )

    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_cities",
        return_value={"123": ["kyiv"]},
    )
    mocker.patch(
    "rentalert.services.aggregator.db.get_distinct_city_slugs",
    return_value=["kyiv"],
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_seen_ids",
        return_value=set(),
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_disabled_sources",
        return_value=set(),
    )
    # Ключове: юзер увімкнув ТІЛЬКИ apartment
    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_categories",
        return_value={"123": {"apartment"}},
    )
    mocker.patch("rentalert.services.aggregator.db.save_listing")

    mock_parser = MagicMock()
    mock_parser.source = Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="X",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment", "room"),
        config={},
    )
    # Парсер повертає ОБИДВА оголошення
    mock_parser.fetch.return_value = [listing, room_listing]

    mocker.patch(
        "rentalert.services.aggregator.PARSER_REGISTRY",
        {"olx_ua": mock_parser},
    )

    client = MagicMock()
    notify = MagicMock()

    stats = run_aggregation_cycle(catalog, client, notify)

    # Обидва збережено в БД
    assert stats.listings_new == 2
    # Але розіслано — тільки одне (apartment)
    assert stats.users_notified == 1
    notify.assert_called_once()

    # Перевіряємо, що надіслано саме квартиру
    sent_listings = notify.call_args[0][2]
    assert len(sent_listings) == 1
    assert sent_listings[0].category == "apartment"


def test_cycle_empty_categories_means_all(catalog, listing, mocker) -> None:
    """Порожній set категорій → усе увімкнено (як у user_svc.get_categories)."""
    room_listing = Listing(
        id="olx_ua:99999",
        source_key="olx_ua",
        city_slug="kyiv",
        title="Room listing",
        price="500",
        location="Kyiv",
        link="https://olx.ua/999",
        photo="",
        rooms="1",
        category="room",
        category_icon="🚪",
        category_label="Кімнати",
        created_at=datetime.now(UTC),
    )

    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_cities",
        return_value={"123": ["kyiv"]},
    )
    mocker.patch(
    "rentalert.services.aggregator.db.get_distinct_city_slugs",
    return_value=["kyiv"],
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_seen_ids",
        return_value=set(),
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_disabled_sources",
        return_value=set(),
    )
    # Ключове: юзер НЕ налаштовував категорії
    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_categories",
        return_value={},  # порожній dict
    )
    mocker.patch("rentalert.services.aggregator.db.save_listing")

    mock_parser = MagicMock()
    mock_parser.source = Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="X",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment", "room"),
        config={},
    )
    mock_parser.fetch.return_value = [listing, room_listing]

    mocker.patch(
        "rentalert.services.aggregator.PARSER_REGISTRY",
        {"olx_ua": mock_parser},
    )

    client = MagicMock()
    notify = MagicMock()

    stats = run_aggregation_cycle(catalog, client, notify)

    assert stats.listings_new == 2
    assert stats.users_notified == 1

    # Отримує ОБИДВА оголошення
    sent_listings = notify.call_args[0][2]
    assert len(sent_listings) == 2
    categories = {lst.category for lst in sent_listings}
    assert categories == {"apartment", "room"}

def test_cycle_parses_distinct_cities_only(catalog, listing, mocker) -> None:
    """500 користувачів на одне місто → парсимо ОДИН раз."""
    # 500 користувачів, усі на kyiv
    many_subs = {str(i): ["kyiv"] for i in range(500)}

    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_cities",
        return_value=many_subs,
    )
    # DISTINCT повертає лише одне місто
    mocker.patch(
        "rentalert.services.aggregator.db.get_distinct_city_slugs",
        return_value=["kyiv"],
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_seen_ids",
        return_value=set(),
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_disabled_sources",
        return_value=set(),
    )
    mocker.patch(
        "rentalert.services.aggregator.db.get_all_user_categories",
        return_value={},
    )
    mocker.patch("rentalert.services.aggregator.db.save_listing")

    mock_parser = MagicMock()
    mock_parser.source = Source(
        key="olx_ua",
        country="ua",
        name="OLX.ua",
        icon="X",
        kind="olx",
        base_url="https://www.olx.ua",
        enabled_by_default=True,
        categories=("apartment",),
        config={},
    )
    mock_parser.fetch.return_value = [listing]

    mocker.patch(
        "rentalert.services.aggregator.PARSER_REGISTRY",
        {"olx_ua": mock_parser},
    )

    client = MagicMock()
    notify = MagicMock()

    stats = run_aggregation_cycle(catalog, client, notify)

    # Парсер викликано РІВНО ОДИН РАЗ, хоч користувачів 500
    assert mock_parser.fetch.call_count == 1
    assert stats.pairs_checked == 1

    # Але розсилка — на всіх 500
    assert notify.call_count == 500 
