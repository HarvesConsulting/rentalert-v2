"""Тести для services/subscription.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from rentalert.services import subscription as sub_svc


# ─── Fake DB (in-memory) ───


class FakeClient:
    """Мінімальна заглушка TursoClient для тестів."""

    def __init__(self, user: dict | None = None) -> None:
        self._user = user or {}

    def execute(self, sql: str, params: list | None = None) -> list[list]:
        # Простий матчинг для get_user / is_premium
        if "FROM user_settings" in sql:
            if not self._user:
                return []
            return [[
                self._user.get("chat_id", "123"),
                self._user.get("country", "ua"),
                self._user.get("language", "uk"),
                1 if self._user.get("is_premium") else 0,
                self._user.get("premium_until"),
                self._user.get("username", ""),
                self._user.get("first_name", ""),
                self._user.get("first_seen"),
                self._user.get("last_seen"),
                self._user.get("message_count", 0),
                self._user.get("trial_ends_at"),
                self._user.get("referred_by"),
                self._user.get("referrals_count", 0),
            ]]
        return []

    def execute_non_query(self, sql: str, params: list | None = None) -> int:
        return 0


# ─── get_access_status ───


def test_access_free_country_ua() -> None:
    """Україна — безкоштовно назавжди."""
    client = FakeClient({"chat_id": "123", "country": "ua"})
    status = sub_svc.get_access_status(client, "123")

    assert status["has_access"] is True
    assert status["reason"] == "free_country"
    assert status["until"] is None
    assert status["days_left"] is None


def test_access_trial_active() -> None:
    """Trial активний — доступ є."""
    trial_end = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    client = FakeClient({
        "chat_id": "123",
        "country": "ro",
        "trial_ends_at": trial_end,
    })
    status = sub_svc.get_access_status(client, "123")

    assert status["has_access"] is True
    assert status["reason"] == "trial"
    assert status["days_left"] in (4, 5)  # залежно від годин


def test_access_trial_expired() -> None:
    """Trial закінчився — доступу немає."""
    trial_end = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    client = FakeClient({
        "chat_id": "123",
        "country": "ro",
        "trial_ends_at": trial_end,
    })
    status = sub_svc.get_access_status(client, "123")

    assert status["has_access"] is False
    assert status["reason"] == "trial_expired"


def test_access_premium_active() -> None:
    """Premium активний — доступ є."""
    premium_until = (datetime.now(UTC) + timedelta(days=20)).isoformat()
    client = FakeClient({
        "chat_id": "123",
        "country": "ro",
        "is_premium": True,
        "premium_until": premium_until,
    })
    status = sub_svc.get_access_status(client, "123")

    assert status["has_access"] is True
    assert status["reason"] == "premium"
    assert status["days_left"] in (19, 20)


def test_access_premium_expired() -> None:
    """Premium закінчився — перевіряємо trial."""
    trial_end = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    premium_until = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    client = FakeClient({
        "chat_id": "123",
        "country": "ro",
        "is_premium": True,
        "premium_until": premium_until,
        "trial_ends_at": trial_end,
    })
    status = sub_svc.get_access_status(client, "123")

    # Має впасти до trial
    assert status["has_access"] is True
    assert status["reason"] == "trial"


def test_access_no_user() -> None:
    """Немає користувача — немає доступу."""
    client = FakeClient({})  # порожній
    status = sub_svc.get_access_status(client, "999")

    assert status["has_access"] is False
    assert status["reason"] == "no_user"


def test_access_no_trial_set() -> None:
    """Trial не встановлено, країна не ua — немає доступу."""
    client = FakeClient({"chat_id": "123", "country": "pl"})
    status = sub_svc.get_access_status(client, "123")

    assert status["has_access"] is False
    assert status["reason"] == "trial_expired"


# ─── _parse_dt ───


def test_parse_dt_iso() -> None:
    """Парсинг ISO-дати."""
    dt = sub_svc._parse_dt("2026-10-03T16:31:34+00:00")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 3


def test_parse_dt_z_suffix() -> None:
    """Парсинг дати з Z-суфіксом."""
    dt = sub_svc._parse_dt("2026-10-03T16:31:34Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_dt_none() -> None:
    """None → None."""
    assert sub_svc._parse_dt(None) is None
    assert sub_svc._parse_dt("") is None
