"""Тести для TelegramNotifier."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rentalert.services.notifier import TelegramNotifier


@pytest.fixture
def notifier() -> TelegramNotifier:
    return TelegramNotifier("123:fake_token")


def test_call_ok(notifier, mocker) -> None:
    """200 OK → True."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True, "result": {}}

    mocker.patch(
        "rentalert.services.notifier.cffi_requests.post",
        return_value=mock_response,
    )

    assert notifier._call("sendMessage", {"chat_id": "1", "text": "hi"}) is True


def test_call_429_retries_once(notifier, mocker) -> None:
    """429 rate limit → чекає retry_after і повторює."""
    # Перший виклик — 429
    resp_429 = MagicMock()
    resp_429.json.return_value = {
        "ok": False,
        "error_code": 429,
        "description": "Too Many Requests: retry after 1",
        "parameters": {"retry_after": 1},
    }
    # Другий виклик — 200 OK
    resp_ok = MagicMock()
    resp_ok.json.return_value = {"ok": True, "result": {}}

    mock_post = mocker.patch(
        "rentalert.services.notifier.cffi_requests.post",
        side_effect=[resp_429, resp_ok],
    )
    mock_sleep = mocker.patch("rentalert.services.notifier.time.sleep")

    result = notifier._call("sendMessage", {"chat_id": "1", "text": "hi"})

    assert result is True
    assert mock_post.call_count == 2  # спочатку 429, потім retry
    mock_sleep.assert_called_once_with(1)  # retry_after = 1


def test_call_403_returns_false(notifier, mocker) -> None:
    """403 (bot blocked) → False, без retry."""
    resp_403 = MagicMock()
    resp_403.json.return_value = {
        "ok": False,
        "error_code": 403,
        "description": "Forbidden: bot was blocked by the user",
    }

    mock_post = mocker.patch(
        "rentalert.services.notifier.cffi_requests.post",
        return_value=resp_403,
    )

    assert notifier._call("sendMessage", {"chat_id": "1", "text": "hi"}) is False
    assert mock_post.call_count == 1  # без retry
