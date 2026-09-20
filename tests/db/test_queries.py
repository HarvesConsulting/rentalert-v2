"""Тести для db/queries.py з in-memory SQLite.

Turso — це libSQL (fork SQLite), тому SQL сумісний.
Замінюємо TursoClient на SQLite-обгортку.
"""

from __future__ import annotations

import sqlite3

import pytest

from rentalert.db import queries as db
from rentalert.db.schema import INDEXES, TABLES


class FakeClient:
    """Замінює TursoClient — використовує in-memory SQLite."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = None  # повертає tuples
        # Створюємо таблиці
        for sql in TABLES:
            self._conn.execute(sql)
        for sql in INDEXES:
            self._conn.execute(sql)
        self._conn.commit()

    def execute(
        self,
        sql: str,
        params: list | None = None,
    ) -> list[list]:
        cur = self._conn.execute(sql, params or [])
        return [list(row) for row in cur.fetchall()]

    def execute_non_query(
        self,
        sql: str,
        params: list | None = None,
    ) -> int:
        cur = self._conn.execute(sql, params or [])
        self._conn.commit()
        return cur.rowcount


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


# ─── User settings ───


def test_ensure_user_creates_record(client) -> None:
    db.ensure_user(client, "123")
    user = db.get_user(client, "123")
    assert user is not None
    assert user["chat_id"] == "123"
    assert user["country"] == "ua"
    assert user["language"] == "uk"


def test_ensure_user_idempotent(client) -> None:
    db.ensure_user(client, "123")
    db.ensure_user(client, "123")
    rows = client.execute("SELECT COUNT(*) FROM user_settings")
    assert rows[0][0] == 1


def test_touch_user_updates_stats(client) -> None:
    db.touch_user(client, "123", username="test", first_name="John")
    db.touch_user(client, "123", username="test", first_name="John")
    user = db.get_user(client, "123")
    assert user is not None
    assert user["message_count"] == 2
    assert user["username"] == "test"


def test_get_user_returns_none_for_missing(client) -> None:
    assert db.get_user(client, "999") is None


def test_set_user_country(client) -> None:
    db.set_user_country(client, "123", "pl")
    assert db.get_user_country(client, "123") == "pl"


def test_get_user_country_default(client) -> None:
    assert db.get_user_country(client, "999") == "ua"


def test_set_user_language(client) -> None:
    db.set_user_language(client, "123", "en")
    assert db.get_user_language(client, "123") == "en"


# ─── User cities ───


def test_add_and_get_user_cities(client) -> None:
    db.add_user_city(client, "123", "kyiv")
    db.add_user_city(client, "123", "lviv")
    cities = db.get_user_cities(client, "123")
    assert cities == ["kyiv", "lviv"]


def test_add_user_city_idempotent(client) -> None:
    db.add_user_city(client, "123", "kyiv")
    db.add_user_city(client, "123", "kyiv")
    assert db.get_user_cities(client, "123") == ["kyiv"]


def test_remove_user_city(client) -> None:
    db.add_user_city(client, "123", "kyiv")
    db.add_user_city(client, "123", "lviv")
    db.remove_user_city(client, "123", "kyiv")
    assert db.get_user_cities(client, "123") == ["lviv"]


def test_clear_user_cities(client) -> None:
    db.add_user_city(client, "123", "kyiv")
    db.add_user_city(client, "123", "lviv")
    db.clear_user_cities(client, "123")
    assert db.get_user_cities(client, "123") == []


def test_get_all_user_cities(client) -> None:
    db.add_user_city(client, "123", "kyiv")
    db.add_user_city(client, "123", "lviv")
    db.add_user_city(client, "456", "warszawa")
    result = db.get_all_user_cities(client)
    assert result == {"123": ["kyiv", "lviv"], "456": ["warszawa"]}


# ─── Disabled sources ───


def test_disable_and_get_sources(client) -> None:
    db.disable_source(client, "123", "dimria")
    db.disable_source(client, "123", "olx_pl")
    assert db.get_disabled_sources(client, "123") == {"dimria", "olx_pl"}


def test_enable_source(client) -> None:
    db.disable_source(client, "123", "dimria")
    db.enable_source(client, "123", "dimria")
    assert db.get_disabled_sources(client, "123") == set()


# ─── Seen listings ───


def test_save_listing(client) -> None:
    affected = db.save_listing(
        client,
        id="olx_ua:1",
        source_key="olx_ua",
        city_slug="kyiv",
        title="Test",
    )
    assert affected == 1
    assert db.is_seen(client, "olx_ua:1")


def test_save_listing_duplicate(client) -> None:
    db.save_listing(client, id="olx_ua:1", source_key="olx_ua", city_slug="kyiv", title="Test")
    affected = db.save_listing(
        client, id="olx_ua:1", source_key="olx_ua", city_slug="kyiv", title="Test"
    )
    assert affected == 0  # вже існує


def test_get_seen_ids(client) -> None:
    db.save_listing(client, id="a", source_key="x", city_slug="y", title="t")
    db.save_listing(client, id="b", source_key="x", city_slug="y", title="t")
    result = db.get_seen_ids(client, ["a", "b", "c"])
    assert result == {"a", "b"}


# ─── Favorites ───


def test_add_and_get_favorites(client) -> None:
    db.save_listing(client, id="olx_ua:1", source_key="olx_ua", city_slug="kyiv", title="T1")
    db.add_favorite(client, "123", "olx_ua:1")
    favs = db.get_favorites(client, "123")
    assert len(favs) == 1
    assert favs[0]["id"] == "olx_ua:1"


def test_is_favorite(client) -> None:
    db.add_favorite(client, "123", "x")
    assert db.is_favorite(client, "123", "x") is True
    assert db.is_favorite(client, "123", "y") is False


def test_remove_favorite(client) -> None:
    db.add_favorite(client, "123", "x")
    db.remove_favorite(client, "123", "x")
    assert db.is_favorite(client, "123", "x") is False


def test_count_favorites(client) -> None:
    db.add_favorite(client, "123", "a")
    db.add_favorite(client, "123", "b")
    assert db.count_favorites(client, "123") == 2


# ─── Activity ───


def test_log_activity(client) -> None:
    db.log_activity(client, "123", "add_city", {"slug": "kyiv"})
    rows = client.execute("SELECT action, details FROM user_activity WHERE chat_id = '123'")
    assert len(rows) == 1
    assert rows[0][0] == "add_city"
    assert "kyiv" in rows[0][1]
