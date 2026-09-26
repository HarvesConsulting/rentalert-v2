"""Логіка підписки та доступу.

Визначає, чи має користувач доступ до платних функцій:
  - розсилка нових оголошень
  - додавання міст

Правила:
  - Україна (ua) — безкоштовно назавжди
  - Інші країни — trial 7 днів, потім premium (Telegram Stars)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from rentalert.db import queries as db
from rentalert.db.client import TursoClient

log = logging.getLogger(__name__)


TRIAL_DAYS = 7
"""Тривалість trial у днях."""


def get_access_status(
    client: TursoClient,
    chat_id: str,
) -> dict[str, Any]:
    """Повертає статус доступу користувача.

    Returns:
        {
            "has_access": bool,
            "reason": "admin" | "free_country" | "premium" | "trial"
                      | "trial_expired" | "no_user",
            "until": iso_datetime | None,
            "days_left": int | None,
        }
    """
    # ── Адмін — завжди доступ ──
    from rentalert import config

    admin_ids = {x.strip() for x in config.ADMIN_CHAT_IDS.split(",") if x.strip()}
    if chat_id in admin_ids:
        return {
            "has_access": True,
            "reason": "admin",
            "until": None,
            "days_left": None,
        }

    user = db.get_user(client, chat_id)
    if not user:
        return {"has_access": False, "reason": "no_user"}

    # ... далі без змін ...
    user = db.get_user(client, chat_id)
    if not user:
        return {"has_access": False, "reason": "no_user"}

    country = user.get("country") or "ua"

    # 1. Україна — завжди безкоштовно
    if country == "ua":
        return {
            "has_access": True,
            "reason": "free_country",
            "until": None,
            "days_left": None,
        }

    # 2. Перевіряємо premium
    if user.get("is_premium"):
        premium_until = user.get("premium_until")
        if premium_until:
            try:
                until_dt = _parse_dt(premium_until)
                if until_dt and until_dt > datetime.now(UTC):
                    days_left = (until_dt - datetime.now(UTC)).days
                    return {
                        "has_access": True,
                        "reason": "premium",
                        "until": premium_until,
                        "days_left": days_left,
                    }
            except Exception as e:
                log.exception("Помилка парсингу premium_until: %s", e)

    # 3. Перевіряємо trial
    trial_ends = user.get("trial_ends_at")
    if trial_ends:
        try:
            trial_dt = _parse_dt(trial_ends)
            if trial_dt and trial_dt > datetime.now(UTC):
                days_left = (trial_dt - datetime.now(UTC)).days
                return {
                    "has_access": True,
                    "reason": "trial",
                    "until": trial_ends,
                    "days_left": days_left,
                }
        except Exception as e:
            log.exception("Помилка парсингу trial_ends_at: %s", e)

    # 4. Немає доступу
    return {
        "has_access": False,
        "reason": "trial_expired",
        "until": trial_ends,
        "days_left": 0,
    }


def ensure_trial(client: TursoClient, chat_id: str) -> None:
    """Дає trial 7 днів, якщо його ще немає.

    Викликається при першому /start після реєстрації.
    Ідемпотентно — не перезаписує існуючий trial.
    """
    user = db.get_user(client, chat_id)
    if not user:
        return

    if user.get("trial_ends_at"):
        return  # trial вже є

    trial_end = (datetime.now(UTC) + timedelta(days=TRIAL_DAYS)).isoformat()
    db.set_trial_ends_at(client, chat_id, trial_end)
    log.info("🎁 Trial %d днів надано для %s", TRIAL_DAYS, chat_id)


def extend_premium(
    client: TursoClient,
    chat_id: str,
    days: int,
) -> str:
    """Продовжує premium на N днів.

    Якщо premium ще активний — додає до поточної дати.
    Інакше — від сьогодні.

    Returns:
        ISO-дата нового закінчення.
    """
    user = db.get_user(client, chat_id)
    now = datetime.now(UTC)

    base = now
    if user and user.get("premium_until"):
        try:
            current_until = _parse_dt(user["premium_until"])
            if current_until and current_until > now:
                base = current_until
        except Exception:
            pass

    new_until = base + timedelta(days=days)
    iso = new_until.isoformat()
    db.set_premium_until(client, chat_id, iso)
    log.info("Premium %s продовжено до %s (+%d днів)", chat_id, iso, days)
    return iso


# ─────────────────────────────────────────────────────────────
# Внутрішнє
# ─────────────────────────────────────────────────────────────


def _parse_dt(value: Any) -> datetime | None:
    """Парсить ISO-дату, додає UTC якщо немає."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    s = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
