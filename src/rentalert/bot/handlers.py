"""Обробка Telegram update'ів (повідомлення).

Не займається callback'ами — тільки текстові повідомлення.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from rentalert.bot import keyboards as kb
from rentalert.bot import states
from rentalert.catalog.catalog import Catalog
from rentalert.db import queries as db
from rentalert.db.client import TursoClient
from rentalert.services import user as user_svc
from rentalert.services.notifier import TelegramNotifier
from rentalert.translations import T

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Контекст
# ─────────────────────────────────────────────────────────────

@dataclass
class BotContext:
    """Залежності, які потрібні handlers + callbacks."""

    client: TursoClient
    catalog: Catalog
    notifier: TelegramNotifier
    admin_chat_id: str = ""


# ─────────────────────────────────────────────────────────────
# Головна точка входу
# ─────────────────────────────────────────────────────────────

def handle_update(update: dict[str, Any], ctx: BotContext) -> None:
    """Обробляє один Telegram update."""
    message = update.get("message")
    if not message:
        return

    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()

    # Оновлюємо статистику користувача
    from_info = message.get("from") or {}
    user_svc.ensure_user(
        ctx.client,
        chat_id,
        username=str(from_info.get("username") or ""),
        first_name=str(from_info.get("first_name") or ""),
    )

    # Відповідь адміна на feedback (з reply)
    if _handle_admin_reply(message, chat_id, text, ctx):
        return

    # FSM — очікування
    if _handle_waiting_state(chat_id, text, ctx):
        return

    # Команди
    if text.startswith("/"):
        _handle_command(chat_id, text, ctx)
        return

    # Кнопки меню
    if _handle_menu_button(chat_id, text, ctx):
        return

    # Невідомий текст — показуємо меню
    _send_main_menu(chat_id, ctx)


# ─────────────────────────────────────────────────────────────
# Команди
# ─────────────────────────────────────────────────────────────

def _handle_command(chat_id: str, text: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)

    if text.startswith("/start"):
        states.clear_state(chat_id)
        # Перший запуск?
        user = db.get_user(ctx.client, chat_id)
        if user is None or not user.get("first_seen"):
            _send_country_selector(chat_id, ctx)
        else:
            _send_main_menu(chat_id, ctx)
        return

    if text.startswith("/help"):
        _send_help(chat_id, ctx)
        return

    if text.startswith("/cities"):
        _send_my_cities(chat_id, ctx)
        return

    if text.startswith("/favorites") or text.startswith("/fav"):
        _send_favorites(chat_id, ctx)
        return

    if text.startswith("/settings"):
        _send_settings(chat_id, ctx)
        return

    if text.startswith("/language") or text.startswith("/lang"):
        _send_language_menu(chat_id, ctx)
        return

    # Невідома команда
    ctx.notifier.send_message(
        chat_id,
        T("unknown_command", lang),
        keyboard=kb.main_menu_keyboard(lang),
    )


# ─────────────────────────────────────────────────────────────
# Кнопки головного меню (reply)
# ─────────────────────────────────────────────────────────────

def _handle_menu_button(chat_id: str, text: str, ctx: BotContext) -> bool:
    lang = user_svc.get_language(ctx.client, chat_id)

    if text == T("btn_my_cities", "uk") or text == T("btn_my_cities", "en"):
        _send_my_cities(chat_id, ctx)
        return True

    if text == T("btn_add_city", "uk") or text == T("btn_add_city", "en"):
        _send_add_city_prompt(chat_id, ctx)
        return True

    if text == T("btn_favorites", "uk") or text == T("btn_favorites", "en"):
        _send_favorites(chat_id, ctx)
        return True

    if text == T("btn_settings", "uk") or text == T("btn_settings", "en"):
        _send_settings(chat_id, ctx)
        return True

    if text == T("btn_help", "uk") or text == T("btn_help", "en"):
        states.clear_state(chat_id)
        _send_help(chat_id, ctx)
        return True

    return False


# ─────────────────────────────────────────────────────────────
# FSM
# ─────────────────────────────────────────────────────────────

def _handle_waiting_state(
    chat_id: str,
    text: str,
    ctx: BotContext,
) -> bool:
    state = states.get_state(chat_id)
    if state is None or text.startswith("/"):
        return False

    lang = user_svc.get_language(ctx.client, chat_id)

    # Натиснув кнопку меню — скасовуємо стан
    if _is_menu_button(text):
        states.clear_state(chat_id)
        return False

    if state == states.STATE_WAITING_CITY:
        _process_city_search(chat_id, text, ctx)
        return True

    if state == states.STATE_WAITING_FEEDBACK:
        _process_feedback(chat_id, text, ctx)
        return True

    return False


def _is_menu_button(text: str) -> bool:
    """Чи це кнопка головного меню (uk або en)."""
    for key in ("btn_my_cities", "btn_add_city", "btn_favorites", "btn_settings", "btn_help"):
        if text in (T(key, "uk"), T(key, "en")):
            return True
    return False


# ─────────────────────────────────────────────────────────────
# Дії
# ─────────────────────────────────────────────────────────────

def _send_main_menu(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    country = user_svc.get_country(ctx.client, chat_id)
    country_label = T(f"country_{country}", lang)

    ctx.notifier.send_message(
        chat_id,
        T("main_menu", lang, country=country_label),
        keyboard=kb.main_menu_keyboard(lang),
    )


def _send_country_selector(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    current = user_svc.get_country(ctx.client, chat_id)

    countries = [
        {
            "code": c.code,
            "name": T(f"country_{c.code}", lang),
            "free": c.free,
            "price_stars": c.price_stars,
        }
        for c in ctx.catalog.all_countries()
    ]

    ctx.notifier.send_message(
        chat_id,
        T("country_selector_title", lang),
        keyboard=kb.country_selector_keyboard(countries, current, lang),
    )


def _send_my_cities(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    cities = user_svc.get_cities(ctx.catalog, ctx.client, chat_id)

    if not cities:
        _send_main_menu_with_text(chat_id, ctx, T("my_cities_empty", lang))
        return

    lines = [T("my_cities_title", lang, count=len(cities)), ""]
    for c in cities:
        region = f" ({c.region})" if c.region else ""
        lines.append(f"• <b>{c.name}</b>{region}")

    ctx.notifier.send_message(
        chat_id,
        "\n".join(lines),
        keyboard=kb.my_cities_keyboard(cities),
    )


def _send_add_city_prompt(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    states.set_state(chat_id, states.STATE_WAITING_CITY)

    ctx.notifier.send_message(
        chat_id,
        T("add_city_prompt", lang),
        keyboard=kb.main_menu_keyboard(lang),
    )


def _send_favorites(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    favs = db.get_favorites(ctx.client, chat_id, limit=20)

    if not favs:
        _send_main_menu_with_text(chat_id, ctx, T("favorites_empty", lang))
        return

    lines = [T("favorites_title", lang, count=len(favs)), ""]
    for f in favs:
        price = f.get("price") or "—"
        title = (f.get("title") or "")[:80]
        lines.append(f"• <b>{price}</b> — {title}")

    buttons = [
        [{"text": T("btn_clear_favorites", lang), "callback_data": "clear_favorites:yes"}],
    ]
    ctx.notifier.send_message(
        chat_id,
        "\n".join(lines),
        keyboard={"inline_keyboard": buttons},
    )


def _send_settings(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    country = user_svc.get_country(ctx.client, chat_id)
    country_label = T(f"country_{country}", lang)

    disabled = user_svc.get_disabled_sources(ctx.client, chat_id)
    total_sources = len(ctx.catalog.all_sources())
    enabled_sources = total_sources - len(disabled)

    ctx.notifier.send_message(
        chat_id,
        T("settings_title", lang, country=country_label),
        keyboard=kb.settings_keyboard(
            country_name=country_label,
            enabled_sources=enabled_sources,
            total_sources=total_sources,
            lang=lang,
        ),
    )


def _send_language_menu(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    current = "Українська" if lang == "uk" else "English"

    ctx.notifier.send_message(
        chat_id,
        T("language_title", lang, current=current),
        keyboard=kb.language_keyboard(),
    )


def _send_help(chat_id: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    ctx.notifier.send_message(
        chat_id,
        T("help_text", lang),
        keyboard=kb.help_keyboard(lang),
    )


def _send_main_menu_with_text(
    chat_id: str,
    ctx: BotContext,
    text: str,
) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    ctx.notifier.send_message(
        chat_id,
        text,
        keyboard=kb.main_menu_keyboard(lang),
    )


# ─────────────────────────────────────────────────────────────
# Пошук міста (FSM)
# ─────────────────────────────────────────────────────────────

def _process_city_search(chat_id: str, query: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    states.clear_state(chat_id)

    if len(query) < 2:
        _send_main_menu_with_text(chat_id, ctx, T("error_short_query", lang))
        return

    country = user_svc.get_country(ctx.client, chat_id)
    matches = ctx.catalog.find_cities(query, country, limit=8)

    if not matches:
        _send_main_menu_with_text(
            chat_id,
            ctx,
            T("error_city_not_found", lang, query=query),
        )
        return

    user_slugs = set(user_svc.get_city_slugs(ctx.client, chat_id))

    ctx.notifier.send_message(
        chat_id,
        T("city_search_results", lang, count=len(matches)),
        keyboard=kb.city_search_results_keyboard(matches, user_slugs),
    )


# ─────────────────────────────────────────────────────────────
# Feedback (FSM)
# ─────────────────────────────────────────────────────────────

def _process_feedback(chat_id: str, text: str, ctx: BotContext) -> None:
    lang = user_svc.get_language(ctx.client, chat_id)
    states.clear_state(chat_id)

    if not text:
        return

    # Логуємо
    db.log_activity(ctx.client, chat_id, "feedback", {"text": text[:200]})

    # Надсилаємо адміну
    if ctx.admin_chat_id:
        user = db.get_user(ctx.client, chat_id)
        username = (user or {}).get("username") or ""
        first_name = (user or {}).get("first_name") or "Користувач"

        admin_text = (
            f"💬 <b>Feedback</b>\n\n"
            f"👤 {first_name}"
            f"{' (@' + username + ')' if username else ''}\n"
            f"🆔 <code>{chat_id}</code>\n\n"
            f"─────────────────\n"
            f"{text}"
        )
        ctx.notifier.send_message(ctx.admin_chat_id, admin_text)

    _send_main_menu_with_text(chat_id, ctx, T("feedback_thanks", lang))


# ─────────────────────────────────────────────────────────────
# Admin reply на feedback
# ─────────────────────────────────────────────────────────────

def _handle_admin_reply(
    message: dict[str, Any],
    chat_id: str,
    text: str,
    ctx: BotContext,
) -> bool:
    """Якщо адмін відповідає на feedback → пересилаємо користувачу."""
    if str(chat_id) != str(ctx.admin_chat_id):
        return False

    replied = message.get("reply_to_message")
    if not replied:
        return False

    replied_text = replied.get("text") or ""

    import re
    match = re.search(r"🆔\s*(\d+)", replied_text)
    if not match or not text:
        return False

    target_id = match.group(1)
    ctx.notifier.send_message(
        target_id,
        f"💬 <b>Відповідь від розробника:</b>\n\n{text}",
    )
    ctx.notifier.send_message(
        chat_id,
        f"✅ Відповідь надіслано користувачу <code>{target_id}</code>",
    )
    return True
