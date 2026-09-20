"""Обробка inline callback'ів від Telegram.

Точка входу: handle_callback(callback, ctx).

Формат callback_data:
    country:ua
    add_city:kyiv
    remove_city:kyiv
    lang:uk | lang:en
    clear_cities:yes | clear_cities:no
    clear_favorites:yes | clear_favorites:no
    cfg:country | cfg:sources | cfg:types | cfg:language | cfg:clear_cities
    toggle_cat:apartment
    save_categories
    toggle_source:kyiv:dimria
    fav:LISTING_ID
    feedback
    rate | rate:5
"""

from __future__ import annotations

import logging
from typing import Any

from rentalert.bot import keyboards as kb
from rentalert.bot import states
from rentalert.bot.handlers import BotContext
from rentalert.db import queries as db
from rentalert.services import user as user_svc
from rentalert.translations import T

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Головна точка входу
# ─────────────────────────────────────────────────────────────


def handle_callback(callback: dict[str, Any], ctx: BotContext) -> None:
    """Обробляє один callback_query."""
    cb_id = callback["id"]
    chat_id = str(callback["from"]["id"])
    data = callback.get("data", "")
    message = callback.get("message") or {}
    message_id = message.get("message_id")

    if not data:
        ctx.notifier.answer_callback(cb_id)
        return

    # Розбиваємо data на частини: "country:ua" → ["country", "ua"]
    parts = data.split(":")
    action = parts[0]
    args = parts[1:]

    try:
        _dispatch(action, args, chat_id, message_id, cb_id, ctx)
    except Exception as e:
        log.exception("Callback error для %s: %s", data, e)
        ctx.notifier.answer_callback(cb_id, T("error_generic", "uk"))


def _dispatch(
    action: str,
    args: list[str],
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Маршрутизація callback за action."""
    if action == "country":
        _handle_country(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "add_city":
        _handle_add_city(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "remove_city":
        _handle_remove_city(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "lang":
        _handle_lang(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "clear_cities":
        _handle_clear_cities(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "clear_favorites":
        _handle_clear_favorites(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "cfg":
        _handle_cfg(args, chat_id, message_id, cb_id, ctx)
        return

    if action == "toggle_cat":
        _handle_toggle_cat(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "save_categories":
        _handle_save_categories(chat_id, message_id, cb_id, ctx)
        return

    if action == "toggle_source":
        _handle_toggle_source(args, chat_id, cb_id, ctx)
        return

    if action == "fav":
        _handle_favorite(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "feedback":
        _handle_feedback(chat_id, cb_id, ctx)
        return

    if action == "rate":
        _handle_rate(args, chat_id, message_id, cb_id, ctx)
        return

    # Невідомий callback
    ctx.notifier.answer_callback(cb_id)


# ─────────────────────────────────────────────────────────────
# country
# ─────────────────────────────────────────────────────────────


def _handle_country(
    country: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Вибір країни."""
    if ctx.catalog.country(country) is None:
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    lang = user_svc.get_language(ctx.client, chat_id)
    old = user_svc.get_country(ctx.client, chat_id)

    if old == country:
        ctx.notifier.answer_callback(cb_id, T(f"country_{country}", lang))
        return

    user_svc.set_country(ctx.client, chat_id, country)
    country_label = T(f"country_{country}", lang)

    db.log_activity(ctx.client, chat_id, "country_change", {"from": old, "to": country})
    ctx.notifier.answer_callback(cb_id, f"✅ {country_label}")

    if message_id:
        text = T("main_menu", lang, country=country_label)
        ctx.notifier.edit_message(
            chat_id,
            message_id,
            text,
            keyboard={"inline_keyboard": []},
        )

    # Показуємо головне меню
    ctx.notifier.send_message(
        chat_id,
        T("main_menu", lang, country=country_label),
        keyboard=kb.main_menu_keyboard(lang),
    )


# ─────────────────────────────────────────────────────────────
# add_city / remove_city
# ─────────────────────────────────────────────────────────────


def _handle_add_city(
    city_slug: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Додає місто."""
    if ctx.catalog.city(city_slug) is None:
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    user_svc.add_city(ctx.client, chat_id, city_slug)
    city = ctx.catalog.city(city_slug)
    name = city.name if city else city_slug
    region = city.region if city else ""

    db.log_activity(
        ctx.client,
        chat_id,
        "add_city",
        {"slug": city_slug, "name": name},
    )
    ctx.notifier.answer_callback(cb_id, f"✅ {name}")

    # Прибираємо клавіатуру вибору і показуємо підтвердження
    if message_id:
        location = f"{name} ({region})" if region else name
        ctx.notifier.edit_message(
            chat_id,
            message_id,
            f"✅ <b>Додано:</b> {location}",
            keyboard={"inline_keyboard": []},
        )


def _handle_remove_city(
    city_slug: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Видаляє місто."""
    user_svc.get_language(ctx.client, chat_id)
    city = ctx.catalog.city(city_slug)
    name = city.name if city else city_slug

    user_svc.remove_city(ctx.client, chat_id, city_slug)
    db.log_activity(ctx.client, chat_id, "remove_city", {"slug": city_slug})
    ctx.notifier.answer_callback(cb_id, f"🗑 {name}")

    if message_id:
        ctx.notifier.edit_message(
            chat_id,
            message_id,
            f"🗑 <b>{name}</b>",
            keyboard={"inline_keyboard": []},
        )


# ─────────────────────────────────────────────────────────────
# lang
# ─────────────────────────────────────────────────────────────


def _handle_lang(
    lang: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Зміна мови."""
    if lang not in ("uk", "en"):
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    user_svc.set_language(ctx.client, chat_id, lang)
    ctx.notifier.answer_callback(cb_id, T("language_changed", lang))

    if message_id:
        ctx.notifier.edit_message(
            chat_id,
            message_id,
            T("language_changed", lang),
            keyboard={"inline_keyboard": []},
        )

    country = user_svc.get_country(ctx.client, chat_id)
    country_label = T(f"country_{country}", lang)
    ctx.notifier.send_message(
        chat_id,
        T("main_menu", lang, country=country_label),
        keyboard=kb.main_menu_keyboard(lang),
    )


# ─────────────────────────────────────────────────────────────
# clear_cities / clear_favorites
# ─────────────────────────────────────────────────────────────


def _handle_clear_cities(
    confirm: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Очищення міст."""
    user_svc.get_language(ctx.client, chat_id)

    if confirm == "yes":
        db.clear_user_cities(ctx.client, chat_id)
        db.log_activity(ctx.client, chat_id, "clear_cities")
        ctx.notifier.answer_callback(cb_id, "🗑")
        if message_id:
            ctx.notifier.edit_message(
                chat_id,
                message_id,
                "🗑 <b>Міста очищено</b>",
                keyboard={"inline_keyboard": []},
            )
    else:
        ctx.notifier.answer_callback(cb_id, "✓")
        if message_id:
            ctx.notifier.edit_message(
                chat_id,
                message_id,
                "✓ Скасовано",
                keyboard={"inline_keyboard": []},
            )


def _handle_clear_favorites(
    confirm: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Очищення обраного."""
    if confirm == "yes":
        db.clear_favorites(ctx.client, chat_id)
        ctx.notifier.answer_callback(cb_id, "🗑")
        if message_id:
            ctx.notifier.edit_message(
                chat_id,
                message_id,
                "🗑 <b>Обране очищено</b>",
                keyboard={"inline_keyboard": []},
            )
    else:
        ctx.notifier.answer_callback(cb_id, "✓")


# ─────────────────────────────────────────────────────────────
# cfg (заглушка — реалізація у частині 2)
# ─────────────────────────────────────────────────────────────


def _handle_cfg(
    args: list[str],
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Налаштування. Тимчасова заглушка — реалізуємо у частині 2."""
    ctx.notifier.answer_callback(cb_id, "⚙️")


# ─────────────────────────────────────────────────────────────
# toggle_cat / save_categories / toggle_source (заглушки)
# ─────────────────────────────────────────────────────────────


def _handle_toggle_cat(
    cat_key: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    ctx.notifier.answer_callback(cb_id, "✅")


def _handle_save_categories(
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    ctx.notifier.answer_callback(cb_id, "💾")


def _handle_toggle_source(
    args: list[str],
    chat_id: str,
    cb_id: str,
    ctx: BotContext,
) -> None:
    ctx.notifier.answer_callback(cb_id, "✅")


# ─────────────────────────────────────────────────────────────
# fav (заглушка — реалізація у частині 2)
# ─────────────────────────────────────────────────────────────


def _handle_favorite(
    listing_id: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Додає/видаляє з обраного."""
    if db.is_favorite(ctx.client, chat_id, listing_id):
        db.remove_favorite(ctx.client, chat_id, listing_id)
        ctx.notifier.answer_callback(cb_id, "🗑")
    else:
        db.add_favorite(ctx.client, chat_id, listing_id)
        ctx.notifier.answer_callback(cb_id, "⭐")
        db.log_activity(ctx.client, chat_id, "add_favorite", {"id": listing_id})


# ─────────────────────────────────────────────────────────────
# feedback / rate
# ─────────────────────────────────────────────────────────────


def _handle_feedback(
    chat_id: str,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Починаємо feedback."""
    lang = user_svc.get_language(ctx.client, chat_id)
    states.set_state(chat_id, states.STATE_WAITING_FEEDBACK)
    ctx.notifier.answer_callback(cb_id)
    ctx.notifier.send_message(
        chat_id,
        T("feedback_prompt", lang),
        keyboard=kb.main_menu_keyboard(lang),
    )


def _handle_rate(
    args: list[str],
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Оцінка бота (args[0] — цифра 1-5, або порожньо)."""
    if not args:
        # Показати вибір
        buttons = [
            [
                {"text": "⭐ 1", "callback_data": "rate:1"},
                {"text": "⭐⭐ 2", "callback_data": "rate:2"},
                {"text": "⭐⭐⭐ 3", "callback_data": "rate:3"},
            ],
            [
                {"text": "⭐⭐⭐⭐ 4", "callback_data": "rate:4"},
                {"text": "⭐⭐⭐⭐⭐ 5", "callback_data": "rate:5"},
            ],
        ]
        ctx.notifier.answer_callback(cb_id)
        if message_id:
            ctx.notifier.edit_message(
                chat_id,
                message_id,
                "⭐ <b>Оцініть бота</b>\n\nНаскільки ймовірно, що ви порекомендуєте його друзям?",
                keyboard={"inline_keyboard": buttons},
            )
        return

    # args[0] — цифра
    try:
        rating = int(args[0])
    except ValueError:
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    if rating < 1 or rating > 5:
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    db.log_activity(ctx.client, chat_id, "rate", {"rating": rating})
    ctx.notifier.answer_callback(cb_id, f"✅ {rating}/5")

    if ctx.admin_chat_id:
        user = db.get_user(ctx.client, chat_id)
        username = (user or {}).get("username") or ""
        first_name = (user or {}).get("first_name") or "?"
        admin_text = (
            f"⭐ <b>Оцінка: {rating}/5</b>\n"
            f"👤 {first_name}"
            f"{' (@' + username + ')' if username else ''}\n"
            f"🆔 <code>{chat_id}</code>"
        )
        ctx.notifier.send_message(ctx.admin_chat_id, admin_text)

    if message_id:
        ctx.notifier.edit_message(
            chat_id,
            message_id,
            f"⭐ <b>Дякую за оцінку {rating}/5!</b>",
            keyboard={"inline_keyboard": []},
        )
