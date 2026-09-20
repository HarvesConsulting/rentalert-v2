"""Конфігурація з env. Заповнимо поетапно."""

import os

# ─── Telegram ───
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

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
