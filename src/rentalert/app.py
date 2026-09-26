"""Flask + Telegram webhook + startup.

app: Flask-застосунок для gunicorn.
Startup запускається ліниво — у worker process при першому запиті.
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
_startup_lock = threading.Lock()
_aggregation_lock = threading.Lock()

AGGREGATION_INTERVAL_MINUTES = 15

DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ─────────────────────────────────────────────────────────────
# Startup (lazy, у worker process)
# ─────────────────────────────────────────────────────────────


def _ensure_startup() -> None:
    """Гарантує, що startup виконано (idempotent, з lock).

    Викликається ліниво при першому запиті до webhook або root.
    Це гарантує, що _ctx створюється у worker process (gunicorn),
    а не у master.
    """
    global _ctx, _scheduler

    with _startup_lock:
        if _ctx is not None:
            return

        log.info("🔄 Startup (worker)...")

        if not config.TURSO_URL or not config.TURSO_TOKEN:
            log.error("TURSO_URL або TURSO_TOKEN не встановлено — вихід")
            return

        client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)
        log.info("✅ Turso client створено")

        init_schema(client)
        log.info("✅ Schema ініціалізовано")

        catalog = Catalog.load(DATA_DIR)
        log.info("✅ Catalog: %s", catalog.stats())

        build_registry(catalog)
        log.info("✅ PARSER_REGISTRY: %d парсерів", len(PARSER_REGISTRY))

        notifier = TelegramNotifier(config.TELEGRAM_BOT_TOKEN)
        log.info("✅ Notifier створено")

        _ctx = BotContext(
            client=client,
            catalog=catalog,
            notifier=notifier,
            admin_chat_id=config.TELEGRAM_CHAT_ID,
        )

        # APScheduler вимкнено — використовуємо cron-job.org (кожні 5 хв).
        # Це запобігає дублюванню агрегації (два процеси одночасно).
        # if _scheduler is None:
        #     _scheduler = BackgroundScheduler()
        #     _scheduler.add_job(
        #         func=_run_aggregation,
        #         trigger="interval",
        #         minutes=AGGREGATION_INTERVAL_MINUTES,
        #         id="aggregation",
        #         replace_existing=True,
        #         max_instances=1,
        #     )
        #     _scheduler.start()
        #     log.info(
        #         "✅ Scheduler запущено (кожні %d хв)",
        #         AGGREGATION_INTERVAL_MINUTES,
        #     )

        _ready.set()
        log.info("🚀 Startup завершено")


def _run_aggregation() -> None:
    """Один цикл агрегації (з lock — запобігає паралельним запускам)."""
    if _ctx is None:
        log.warning("_ctx не готовий — пропускаю агрегацію")
        return

    # Якщо вже запущено — пропускаємо
    if not _aggregation_lock.acquire(blocking=False):
        log.info("⏭ Агрегація вже запущена — пропускаю")
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
    finally:
        _aggregation_lock.release()


def _notify_user(chat_id: str, city_slug: str, listings: list[Any]) -> None:
    """Callback для агрегатора: надсилає сповіщення користувачу."""
    if _ctx is None:
        return

    lang = user_svc.get_language(_ctx.client, chat_id)
    city = _ctx.catalog.city(city_slug)
    city_name = city.name if city else city_slug

    header = T("notification_header", lang, city=city_name, count=len(listings))
    _ctx.notifier.send_message(chat_id, header)

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

        buttons = [
            [
                {
                    "text": T("btn_add_favorite", lang),
                    "callback_data": f"fav:{lst.id}",
                },
                {
                    "text": T("btn_ignore", lang),
                    "callback_data": f"ign:{lst.id}",
                },
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


@app.route("/api/check-all")
def api_check_all() -> tuple[str, int]:
    """Примусовий запуск агрегації (для cron-job.org).

    Це НЕ health check — це реальна робота.
    Render бачить зовнішній трафік і не засинає.
    """
    if _ctx is None:
        try:
            _ensure_startup()
        except Exception as e:
            log.exception("Startup failed у /api/check-all: %s", e)
            return "startup failed", 503

    if _ctx is None:
        return "not ready", 503

    # Запускаємо у фоновому потоці, щоб не блокувати HTTP-відповідь
    threading.Thread(target=_run_aggregation, daemon=True).start()

    return "ok", 200


@app.route("/api/wake")
def api_wake() -> tuple[str, int]:
    """Швидкий endpoint для cron-job.org.

    Миттєво повертає 200 і запускає startup + агрегацію у фоні.
    """
    if _ctx is None:
        try:
            _ensure_startup()
        except Exception as e:
            log.exception("Startup failed у /api/wake: %s", e)
            return "startup failed", 503

    if _ctx is None:
        return "not ready", 503

    # Миттєво повертаємо 200 + агрегація у фоні
    threading.Thread(target=_run_aggregation, daemon=True).start()

    return "ok", 200


@app.route("/")
def root() -> Any:
    """Корінь — базова інформація."""
    if _ctx is None:
        try:
            _ensure_startup()
        except Exception as e:
            log.exception("Startup failed: %s", e)

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
        try:
            _ensure_startup()
        except Exception as e:
            log.exception("Startup failed: %s", e)
            return "startup failed", 503

    if _ctx is None:
        return "not ready", 503

    # ── Перевірка секрету від Telegram ──
    # Якщо WEBHOOK_SECRET встановлено — перевіряємо header.
    # Якщо ні — пропускаємо (для локальної розробки).
    if config.WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != config.WEBHOOK_SECRET:
            log.warning(
                "Webhook: невірний secret_token від %s",
                request.remote_addr,
            )
            return "forbidden", 403

    update = request.get_json(silent=True) or {}

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
        log.error("❌ _safe_handle_callback: _ctx is None!")
        return
    try:
        log.info("→ callback: %s", callback.get("data"))
        handle_callback(callback, _ctx)
        log.info("✓ callback ok")
    except Exception as e:
        log.exception("Callback error: %s", e)


def _safe_handle_message(update: dict[str, Any]) -> None:
    """Обгортка з try/except для message."""
    if _ctx is None:
        log.error("❌ _safe_handle_message: _ctx is None!")
        return
    try:
        msg = update.get("message", {})
        log.info("→ message: %s", (msg.get("text") or "")[:50])
        handle_update(update, _ctx)
        log.info("✓ message ok")
    except Exception as e:
        log.exception("Update error: %s", e)


@app.route("/api/stats")
def api_stats() -> Any:
    """Проста статистика (для адміна)."""
    if _ctx is None:
        try:
            _ensure_startup()
        except Exception as e:
            log.exception("Startup failed: %s", e)
            return jsonify({"error": "startup failed"}), 503

    if _ctx is None:
        return jsonify({"error": "not ready"}), 503

    if config.ADMIN_API_TOKEN:
        token = request.args.get("token") or request.headers.get("X-Admin-Token", "")
        if token != config.ADMIN_API_TOKEN:
            return jsonify({"error": "unauthorized"}), 401

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


@app.route("/api/debug/njuskalo")
def debug_njuskalo() -> Any:
    """Тимчасово: перевірити, що повертає NJUSKALO з Render."""
    from bs4 import BeautifulSoup
    from curl_cffi import requests as cffi_requests

    url = "https://www.njuskalo.hr/iznajmljivanje-stanova/zagreb"
    try:
        r = cffi_requests.get(url, impersonate="chrome", timeout=30)
    except Exception as e:
        return jsonify({"error": str(e)})

    soup = BeautifulSoup(r.text, "html.parser")

    items_regular = soup.find_all(
        "li",
        class_=lambda x: x and "EntityList-item" in x and "EntityList-item--Regular" in x,
    )
    items_all = soup.find_all(
        "li",
        class_=lambda x: x and "EntityList-item" in x,
    )

    return jsonify(
        {
            "url": url,
            "status": r.status_code,
            "size": len(r.text),
            "title": ((soup.title.string or "") if soup.title else "")[:200],
            "items_regular": len(items_regular),
            "items_all": len(items_all),
            "text_sample": r.text[:1000],
        }
    )


@app.route("/api/debug/sources")
def debug_sources() -> Any:
    """Перевіряє, які джерела доступні з Render."""
    from bs4 import BeautifulSoup
    from curl_cffi import requests as cffi_requests

    results: dict[str, Any] = {}

    # OLX.ua API
    try:
        r = cffi_requests.get(
            "https://www.olx.ua/api/v1/offers/",
            params={"city_id": 268, "category_id": 1760, "limit": 3},
            impersonate="chrome",
            timeout=30,
        )
        results["olx_ua"] = {
            "status": r.status_code,
            "size": len(r.text),
            "is_json": r.text.strip().startswith("{"),
            "preview": r.text[:150],
        }
    except Exception as e:
        results["olx_ua"] = {"error": str(e)}

    # Kleinanzeigen
    try:
        r = cffi_requests.get(
            "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331",
            impersonate="chrome",
            timeout=30,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string if soup.title and soup.title.string else ""
        results["kleinanzeigen"] = {
            "status": r.status_code,
            "size": len(r.text),
            "title": title[:100],
            "articles": len(soup.find_all("article")),
        }
    except Exception as e:
        results["kleinanzeigen"] = {"error": str(e)}

    # Habitaclia
    try:
        r = cffi_requests.get(
            "https://www.habitaclia.com/alquiler-madrid.htm",
            impersonate="chrome",
            timeout=30,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string if soup.title and soup.title.string else ""
        results["habitaclia"] = {
            "status": r.status_code,
            "size": len(r.text),
            "title": title[:100],
            "articles": len(soup.find_all("article")),
        }
    except Exception as e:
        results["habitaclia"] = {"error": str(e)}

    return jsonify(results)


@app.route("/api/users")
def api_users() -> Any:
    """Список користувачів (тільки для адміна)."""
    if _ctx is None:
        try:
            _ensure_startup()
        except Exception as e:
            log.exception("Startup failed: %s", e)
            return jsonify({"error": "startup failed"}), 503

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
# Startup запускається ліниво — при першому запиті до webhook/root
# (у worker process gunicorn, а не в master)
# ─────────────────────────────────────────────────────────────
