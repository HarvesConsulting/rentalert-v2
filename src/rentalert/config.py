"""Конфігурація з env + .env файлу."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Завантажуємо .env з кореня проєкту
_PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


# ─── Telegram ───
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")
ADMIN_CHAT_IDS: str = os.environ.get("ADMIN_CHAT_IDS", "")  # ← НОВИЙ рядок

# ─── Turso ───
TURSO_URL: str = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN: str = os.environ.get("TURSO_AUTH_TOKEN", "")

# ─── DIM.RIA ───
DIMRIA_API_KEY: str = os.environ.get("DIMRIA_API_KEY", "")

# ─── Admin API ───
ADMIN_API_TOKEN: str = os.environ.get("ADMIN_API_TOKEN", "")

# ─── Application ───
PORT: int = int(os.environ.get("PORT", "3000"))
RENDER_EXTERNAL_URL: str = os.environ.get("RENDER_EXTERNAL_URL", "")
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
