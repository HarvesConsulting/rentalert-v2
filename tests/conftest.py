"""Спільні фікстури для тестів. Заповнимо поетапно."""

from pathlib import Path

import pytest


@pytest.fixture
def data_dir() -> Path:
    """Шлях до тестових даних (JSON, HTML-фікстури)."""
    return Path(__file__).parent / "fixtures"
