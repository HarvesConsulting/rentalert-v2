"""Flask + Telegram webhook + startup.

app: Flask-застосунок для gunicorn.
create_app(): factory.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request

from rentalert import config
from rentalert.bot.callbacks import handle_callback
from rentalert.bot.handlers import BotContext, handle_update
from rentalert.catalog.catalog import Catalog
from rentalert.db.client import TursoClient
from rentalert.db.schema import init_schema
from rentalert.parsers.registry import PARSER_REGISTRY, build_registry
from rentalert.services import user as user_svc
from rentalert.services.aggregator import run_aggregation_cycle
from rentalert.services.notifier import TelegramNotifier
from rentalert.translations import T

# ─────────────────────────────────────────────────────────────
# Логування
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Глобальний стан
# ─────────────────────────────────────────────────────────────

_ctx: BotContext | None = None
_scheduler: BackgroundScheduler | None = None
_ready = threading.Event()

AGGREGATION_INTERVAL_MINUTES = 2

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ─────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────


def _startup() -> None:
    """Ініціалізація у фоновому потоці."""
    global _ctx, _scheduler

    log.info("🔄 Startup...")

    # 1. Turso
    if not config.TURSO_URL or not config.TURSO_TOKEN:
        log.error("TURSO_URL або TURSO_TOKEN не встановлено — вихід")
        return

    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)
    log.info("✅ Turso client створено")

    # 2. Schema
    init_schema(client)
    log.info("✅ Schema ініціалізовано")

    # 3. Catalog
    catalog = Catalog.load(DATA_DIR)
    log.info("✅ Catalog: %s", catalog.stats())

    # 4. Parser registry
    build_registry(catalog)
    log.info("✅ PARSER_REGISTRY: %d парсерів", len(PARSER_REGISTRY))

    # 5. Notifier
    notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN)
    log.info("✅ Notifier створено")

    # 6. Контекст
    _ctx = BotContext(
        client=client,
        catalog=catalog,
        notifier=notifier,
        admin_chat_id=config.TELEGRAM_CHAT_ID,
    )

    # 7. Scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        func=_run_aggregation,
        trigger="interval",
        minutes=AGGREGATION_INTERVAL_MINUTES,
        id="aggregation",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    log.info("✅ Scheduler запущено (кожні %d хв)", AGGREGATION_INTERVAL_MINUTES)

    _ready.set()
    log.info("🚀 Startup завершено")


def _run_aggregation() -> None:
    """Один цикл агрегації."""
    if _ctx is None:
        log.warning("_ctx не готовий — пропускаю агрегацію")
        return

    try:
        stats = run_aggregation_cycle(
            _ctx.catalog,
            _ctx.client,
            notify_fn=_notify_user,
        )
        log.info("Агрегація: %s", stats)
    except Exception as e:
        log.exception("Агрегація впала: %s", e)


def _notify_user(chat_id: str, city_slug: str, listings: list[Any]) -> None:
    """Callback для агрегатора: надсилає сповіщення користувачу."""
    if _ctx is None:
        return

    lang = user_svc.get_language(_ctx.client, chat_id)
    city = _ctx.catalog.city(city_slug)
    city_name = city.name if city else city_slug

    # Заголовок
    header = T("notification_header", lang, city=city_name, count=len(listings))
    _ctx.notifier.send_message(chat_id, header)

    # Оголошення (топ-5)
    for i, lst in enumerate(listings[:5], 1):
        icon = lst.category_icon or "🏠"
        price = lst.price or "—"
        title = (lst.title or "")[:100]
        location = lst.location or ""
        link = lst.link or ""
        photo = lst.photo or ""

        lines = [f"{icon} <b>{i}. {price}</b>"]
        if lst.rooms:
            lines.append(f"🛏 {lst.rooms} кімн.")
        lines.append(title)
        if location:
            lines.append(f"📍 {location}")
        if link:
            lines.append(f'🔗 <a href="{link}">Відкрити</a>')

        caption = "\n".join(lines)

        # Кнопка обране
        buttons = [
            [
                {
                    "text": T("btn_add_favorite", lang),
                    "callback_data": f"fav:{lst.id}",
                }
            ]
        ]
        keyboard = {"inline_keyboard": buttons}

        _ctx.notifier.send_photo_or_message(
            chat_id,
            photo,
            caption,
            keyboard=keyboard,
        )

    if len(listings) > 5:
        _ctx.notifier.send_message(
            chat_id,
            T("notification_more", lang, count=len(listings) - 5),
        )


# ─────────────────────────────────────────────────────────────
# Flask app
# ─────────────────────────────────────────────────────────────

app = Flask(__name__)
app.json.ensure_ascii = False  # type: ignore[attr-defined]


@app.route("/health")
def health() -> tuple[str, int]:
    """Health check для Render."""
    return "ok", 200


@app.route("/")
def root() -> Any:
    """Корінь — базова інформація."""
    return jsonify(
        {
            "status": "ok",
            "ready": _ready.is_set(),
            "catalog": _ctx.catalog.stats() if _ctx else None,
        }
    )


@app.route("/telegram/webhook", methods=["POST"])
def telegram_webhook() -> tuple[str, int]:
    """Telegram webhook."""
    if _ctx is None:
        return "not ready", 503

    update = request.get_json(silent=True) or {}

    # Обробка у фоні (щоб Telegram не чекав)
    if "callback_query" in update:
        threading.Thread(
            target=_safe_handle_callback,
            args=(update["callback_query"],),
            daemon=True,
        ).start()
    elif "message" in update:
        threading.Thread(
            target=_safe_handle_message,
            args=(update,),
            daemon=True,
        ).start()

    return "ok", 200


def _safe_handle_callback(callback: dict[str, Any]) -> None:
    """Обгортка з try/except для callback."""
    if _ctx is None:
        return
    try:
        handle_callback(callback, _ctx)
    except Exception as e:
        log.exception("Callback error: %s", e)


def _safe_handle_message(update: dict[str, Any]) -> None:
    """Обгортка з try/except для message."""
    if _ctx is None:
        return
    try:
        handle_update(update, _ctx)
    except Exception as e:
        log.exception("Update error: %s", e)


@app.route("/api/stats")
def api_stats() -> Any:
    """Проста статистика (для адміна)."""
    if _ctx is None:
        return jsonify({"error": "not ready"}), 503

    # Перевірка токена
    if config.ADMIN_API_TOKEN:
        token = request.args.get("token") or request.headers.get("X-Admin-Token", "")
        if token != config.ADMIN_API_TOKEN:
            return jsonify({"error": "unauthorized"}), 401

    # Топ-дії за останні 24 год
    rows = _ctx.client.execute(
        """
        SELECT action, COUNT(*) as cnt
        FROM user_activity
        WHERE created_at >= datetime('now', '-1 day')
        GROUP BY action
        ORDER BY cnt DESC
        LIMIT 10
        """
    )
    actions = [{"action": r[0], "count": int(r[1])} for r in rows]

    total_users = _ctx.client.execute("SELECT COUNT(*) FROM user_settings")
    total_cities = _ctx.client.execute("SELECT COUNT(*) FROM user_cities")
    total_listings = _ctx.client.execute("SELECT COUNT(*) FROM seen_listings")

    return jsonify(
        {
            "status": "ok",
            "users": int(total_users[0][0]) if total_users else 0,
            "user_cities": int(total_cities[0][0]) if total_cities else 0,
            "seen_listings": int(total_listings[0][0]) if total_listings else 0,
            "actions_24h": actions,
        }
    )


@app.route("/api/users")
def api_users() -> Any:
    """Список користувачів (тільки для адміна)."""
    if _ctx is None:
        return jsonify({"error": "not ready"}), 503

    if config.ADMIN_API_TOKEN:
        token = request.args.get("token") or request.headers.get("X-Admin-Token", "")
        if token != config.ADMIN_API_TOKEN:
            return jsonify({"error": "unauthorized"}), 401

    rows = _ctx.client.execute(
        """
        SELECT chat_id, country, language, username, first_name, last_seen, message_count
        FROM user_settings
        ORDER BY last_seen DESC
        LIMIT 100
        """
    )
    users = [
        {
            "chat_id": r[0],
            "country": r[1],
            "language": r[2],
            "username": r[3],
            "first_name": r[4],
            "last_seen": r[5],
            "message_count": r[6] or 0,
        }
        for r in rows
    ]
    return jsonify({"success": True, "count": len(users), "users": users})


# ─────────────────────────────────────────────────────────────
# Запуск startup у фоні
# ─────────────────────────────────────────────────────────────

threading.Thread(target=_startup, daemon=True).start()
