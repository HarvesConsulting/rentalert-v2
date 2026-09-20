"""Тести для TursoClient."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rentalert.db.client import TursoClient, TursoError


def test_client_requires_url_and_token() -> None:
    """Порожній url або token → ValueError."""
    with pytest.raises(ValueError):
        TursoClient("", "token")
    with pytest.raises(ValueError):
        TursoClient("url", "")


def test_client_normalizes_url() -> None:
    """libsql:// → https://."""
    c = TursoClient("libsql://test.turso.io", "token")
    assert c._base_url == "https://test.turso.io"


def test_encode_arg_null() -> None:
    assert TursoClient._encode_arg(None) == {"type": "null"}


def test_encode_arg_bool() -> None:
    assert TursoClient._encode_arg(True) == {"type": "integer", "value": "1"}
    assert TursoClient._encode_arg(False) == {"type": "integer", "value": "0"}


def test_encode_arg_int() -> None:
    assert TursoClient._encode_arg(42) == {"type": "integer", "value": "42"}


def test_encode_arg_float() -> None:
    assert TursoClient._encode_arg(3.14) == {"type": "float", "value": "3.14"}


def test_encode_arg_str() -> None:
    assert TursoClient._encode_arg("hello") == {"type": "text", "value": "hello"}


def test_execute_returns_rows(mocker) -> None:
    """execute повертає список рядків."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "type": "ok",
                "response": {
                    "type": "execute",
                    "result": {
                        "rows": [
                            [{"value": "1"}, {"value": "kyiv"}],
                            [{"value": "2"}, {"value": "lviv"}],
                        ]
                    },
                },
            }
        ]
    }

    mocker.patch(
        "rentalert.db.client.cffi_requests.post",
        return_value=mock_response,
    )

    client = TursoClient("libsql://test.turso.io", "token")
    rows = client.execute("SELECT id, name FROM cities")

    assert rows == [["1", "kyiv"], ["2", "lviv"]]


def test_execute_non_query(mocker) -> None:
    """execute_non_query повертає affected_row_count."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "type": "ok",
                "response": {
                    "type": "execute",
                    "result": {"affected_row_count": 3},
                },
            }
        ]
    }

    mocker.patch(
        "rentalert.db.client.cffi_requests.post",
        return_value=mock_response,
    )

    client = TursoClient("libsql://test.turso.io", "token")
    count = client.execute_non_query("INSERT INTO cities VALUES (?)", ["kyiv"])

    assert count == 3


def test_execute_raises_on_http_error(mocker) -> None:
    """HTTP 500 → TursoError."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mocker.patch(
        "rentalert.db.client.cffi_requests.post",
        return_value=mock_response,
    )

    client = TursoClient("libsql://test.turso.io", "token")

    with pytest.raises(TursoError):
        client.execute("SELECT 1")
