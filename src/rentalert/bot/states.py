"""FSM-стани користувачів (у пам'яті).

Невелике сховище для «очікування вводу»:
    set_state(chat_id, "waiting_city")
    state = get_state(chat_id)
    clear_state(chat_id)

При перезапуску застосунку стан скидається.
Це нормально — очікування недовге (хвилина).
"""

from __future__ import annotations

import threading

# Стани
STATE_WAITING_CITY = "waiting_city"
STATE_WAITING_FEEDBACK = "waiting_feedback"

_states: dict[str, str] = {}
_lock = threading.Lock()


def set_state(chat_id: str | int, state: str) -> None:
    """Встановити стан."""
    with _lock:
        _states[str(chat_id)] = state


def get_state(chat_id: str | int) -> str | None:
    """Отримати стан (або None)."""
    with _lock:
        return _states.get(str(chat_id))


def clear_state(chat_id: str | int) -> None:
    """Скинути стан."""
    with _lock:
        _states.pop(str(chat_id), None)


def clear_all() -> None:
    """Очистити всі стани (для тестів)."""
    with _lock:
        _states.clear()
