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
    ign:LISTING_ID
    unign:LISTING_ID
    feedback
    rate | rate:5
"""

from __future__ import annotations

import logging
from typing import Any

from rentalert.bot import keyboards as kb
from rentalert.bot import states
from rentalert.bot.handlers import (
    BotContext,
    _send_favorites,
    _send_ignored,
    _send_my_cities,
)
from rentalert.db import queries as db
from rentalert.services import user as user_svc
from rentalert.services.aggregator import fetch_city_now
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

    if action == "clear_ignored":
        _handle_clear_ignored(args[0], chat_id, message_id, cb_id, ctx)
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

    if action == "subs":
        _handle_subs(args[0], chat_id, cb_id, ctx)
        return

    if action == "buy":
        _handle_buy(args[0], chat_id, cb_id, ctx)
        return

    if action == "ign":
        _handle_ignore(args[0], chat_id, message_id, cb_id, ctx)
        return

    if action == "unign":
        _handle_unignore(args[0], chat_id, message_id, cb_id, ctx)
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

    old = user_svc.get_country(ctx.client, chat_id)

    if old == country:
        lang = user_svc.get_language(ctx.client, chat_id)
        ctx.notifier.answer_callback(cb_id, T(f"country_{country}", lang))
        return

    # Змінюємо країну (це також виставить мову за замовчуванням)
    user_svc.set_country(ctx.client, chat_id, country)

    # Після зміни країни — беремо НОВУ мову
    lang = user_svc.get_language(ctx.client, chat_id)
    country_label = T(f"country_{country}", lang)

    db.log_activity(
        ctx.client,
        chat_id,
        "country_change",
        {"from": old, "to": country},
    )

    # Toast (не повідомлення у чаті)
    ctx.notifier.answer_callback(cb_id, f"✅ {country_label}")

    # Одне повідомлення — головне меню
    from rentalert.bot.handlers import _send_main_menu

    _send_main_menu(chat_id, ctx)


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
    """Додає місто і одразу показує свіжі оголошення."""
    if ctx.catalog.city(city_slug) is None:
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    # ── Перевірка доступу ──
    from rentalert.services import subscription as sub_svc

    status = sub_svc.get_access_status(ctx.client, chat_id)
    if not status["has_access"]:
        lang = user_svc.get_language(ctx.client, chat_id)
        ctx.notifier.answer_callback(cb_id, "🔒")
        ctx.notifier.send_message(
            chat_id,
            T("access_trial_expired", lang),
        )
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

    # Прибираємо клавіатуру вибору
    if message_id:
        location = f"{name} ({region})" if region else name
        ctx.notifier.edit_message(
            chat_id,
            message_id,
            f"✅ <b>Додано:</b> {location}",
            keyboard={"inline_keyboard": []},
        )

    lang = user_svc.get_language(ctx.client, chat_id)

    # ── Перший показ ──
    ctx.notifier.send_message(
        chat_id,
        T("first_show_loading", lang, city=name),
    )

    try:
        listings = fetch_city_now(ctx.catalog, ctx.client, city_slug)
    except Exception as e:
        log.exception("fetch_city_now failed: %s", e)
        listings = []

    if not listings:
        ctx.notifier.send_message(
            chat_id,
            T("first_show_empty", lang, city=name),
        )
        return

    # Показуємо перші 5
    shown = listings[:5]
    ctx.notifier.send_message(
        chat_id,
        T("first_show_header", lang, city=name, count=len(shown)),
    )

    for i, lst in enumerate(shown, 1):
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

        ctx.notifier.send_photo_or_message(
            chat_id,
            photo,
            caption,
            keyboard=keyboard,
        )

    # Фінальне пояснення
    ctx.notifier.send_message(
        chat_id,
        T("first_show_footer", lang),
        keyboard=kb.main_menu_keyboard(lang),
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

    from rentalert.bot.handlers import _send_main_menu

    _send_main_menu(chat_id, ctx)


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


def _handle_clear_ignored(
    confirm: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Очищення ігнорованих оголошень."""
    lang = user_svc.get_language(ctx.client, chat_id)

    if confirm == "yes":
        n = db.count_ignored(ctx.client, chat_id)
        db.clear_ignored(ctx.client, chat_id)
        db.log_activity(ctx.client, chat_id, "clear_ignored", {"count": n})
        ctx.notifier.answer_callback(cb_id, "🗑")
        if message_id:
            ctx.notifier.edit_message(
                chat_id,
                message_id,
                T("ignored_cleared", lang, count=n),
                keyboard={"inline_keyboard": []},
            )
    else:
        ctx.notifier.answer_callback(cb_id, "✓")
        if message_id:
            ctx.notifier.edit_message(
                chat_id,
                message_id,
                "✓",
                keyboard={"inline_keyboard": []},
            )


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
    """Меню налаштувань."""
    if not args:
        ctx.notifier.answer_callback(cb_id)
        return

    sub = args[0]
    lang = user_svc.get_language(ctx.client, chat_id)

    if sub == "country":
        ctx.notifier.answer_callback(cb_id)
        _show_country_selector(chat_id, ctx)
        return

    if sub == "language":
        ctx.notifier.answer_callback(cb_id)
        current = "Українська" if lang == "uk" else "English"
        ctx.notifier.send_message(
            chat_id,
            T("language_title", lang, current=current),
            keyboard=kb.language_keyboard(),
        )
        return

    if sub == "clear_cities":
        ctx.notifier.answer_callback(cb_id)
        ctx.notifier.send_message(
            chat_id,
            "🗑 Очистити всі міста?",
            keyboard=kb.confirm_keyboard("clear_cities", lang),
        )
        return

    if sub == "types":
        ctx.notifier.answer_callback(cb_id)
        _show_categories(chat_id, ctx)
        return

    if sub == "sources":
        ctx.notifier.answer_callback(cb_id)
        _show_sources_menu(chat_id, ctx)
        return

    ctx.notifier.answer_callback(cb_id)


def _show_country_selector(chat_id: str, ctx: BotContext) -> None:
    """Показує вибір країни (завжди нове повідомлення)."""
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

    text = T("country_selector_title", lang)
    keyboard = kb.country_selector_keyboard(countries, current, lang)
    ctx.notifier.send_message(chat_id, text, keyboard=keyboard)


def _show_categories(chat_id: str, ctx: BotContext) -> None:
    """Показує категорії (завжди нове повідомлення)."""
    lang = user_svc.get_language(ctx.client, chat_id)
    country = user_svc.get_country(ctx.client, chat_id)
    enabled = user_svc.get_categories(ctx.client, chat_id, country)

    text = T("btn_types", lang)
    keyboard = kb.categories_keyboard(ctx.catalog, country, enabled, lang)
    ctx.notifier.send_message(chat_id, text, keyboard=keyboard)


def _show_sources_menu(chat_id: str, ctx: BotContext) -> None:
    """Показує джерела для міст користувача."""
    lang = user_svc.get_language(ctx.client, chat_id)
    cities = user_svc.get_cities(ctx.catalog, ctx.client, chat_id)

    if not cities:
        ctx.notifier.send_message(
            chat_id,
            T("my_cities_empty", lang),
            keyboard=kb.main_menu_keyboard(lang),
        )
        return

    disabled = user_svc.get_disabled_sources(ctx.client, chat_id)

    lines = ["📡 <b>Джерела</b>", ""]
    for city in cities:
        lines.append(f"<b>{city.name}</b>:")
        for source_key in city.refs:
            source = ctx.catalog.source(source_key)
            if source is None:
                continue
            check = "⬜" if source_key in disabled else "✅"
            lines.append(f"  {check} {source.icon} {source.name}")
        lines.append("")

    text = "\n".join(lines)

    buttons: list[list[dict[str, str]]] = []
    first_city = cities[0]
    for source_key in first_city.refs:
        source = ctx.catalog.source(source_key)
        if source is None:
            continue
        check = "⬜" if source_key in disabled else "✅"
        buttons.append(
            [
                {
                    "text": f"{check} {source.icon} {source.name}",
                    "callback_data": f"toggle_source:{first_city.slug}:{source_key}",
                }
            ]
        )

    ctx.notifier.send_message(
        chat_id,
        text,
        keyboard={"inline_keyboard": buttons},
    )


def _handle_toggle_cat(
    cat_key: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Перемикає категорію."""
    country = user_svc.get_country(ctx.client, chat_id)
    user_svc.toggle_category(ctx.client, chat_id, country, cat_key)
    ctx.notifier.answer_callback(cb_id, "✅")

    if message_id:
        enabled = user_svc.get_categories(ctx.client, chat_id, country)
        kb_dict = kb.categories_keyboard(ctx.catalog, country, enabled, "uk")
        ctx.notifier.edit_reply_markup(chat_id, message_id, kb_dict)


def _handle_save_categories(
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Зберігає категорії."""
    lang = user_svc.get_language(ctx.client, chat_id)
    country = user_svc.get_country(ctx.client, chat_id)
    enabled = user_svc.get_categories(ctx.client, chat_id, country)

    db.log_activity(ctx.client, chat_id, "save_categories", {"enabled": list(enabled)})
    ctx.notifier.answer_callback(cb_id, "💾")

    if message_id:
        ctx.notifier.edit_message(
            chat_id,
            message_id,
            T("btn_save_categories", lang) + " ✅",
            keyboard={"inline_keyboard": []},
        )


def _handle_toggle_source(
    args: list[str],
    chat_id: str,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Перемикає джерело для міста (args: [city_slug, source_key])."""
    if len(args) != 2:
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    _city_slug, source_key = args
    new_state = user_svc.toggle_source(ctx.client, chat_id, source_key)
    ctx.notifier.answer_callback(cb_id, "✅" if new_state else "⬜")


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
# subs (Мої підписки)
# ─────────────────────────────────────────────────────────────


def _handle_subs(
    sub: str,
    chat_id: str,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Обробляє inline-меню «Мої підписки»."""
    ctx.notifier.answer_callback(cb_id)

    if sub == "my_cities":
        _send_my_cities(chat_id, ctx)
    elif sub == "favorites":
        _send_favorites(chat_id, ctx)
    elif sub == "ignored":
        _send_ignored(chat_id, ctx)
    elif sub == "subscription":
        from rentalert.bot.handlers import _send_subscription_status

        _send_subscription_status(chat_id, ctx)


# ─────────────────────────────────────────────────────────────
# ign / unign
# ─────────────────────────────────────────────────────────────


def _handle_ignore(
    listing_id: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Додає оголошення в ігнор-лист користувача."""
    lang = user_svc.get_language(ctx.client, chat_id)

    row = db.get_listing(ctx.client, listing_id)
    if row is None:
        ctx.notifier.answer_callback(cb_id, T("error_listing_not_found", lang))
        return

    fp = db.make_fingerprint(row["title"], row["location"])
    db.add_ignored(ctx.client, chat_id, listing_id, fp)
    db.log_activity(
        ctx.client,
        chat_id,
        "ignore",
        {"listing_id": listing_id, "fingerprint": fp},
    )

    # Прибираємо кнопки з повідомлення, щоб не натиснули ще раз
    if message_id:
        ctx.notifier.edit_reply_markup(
            chat_id,
            message_id,
            {"inline_keyboard": []},
        )

    ctx.notifier.answer_callback(cb_id, T("ignored_done", lang))


def _handle_unignore(
    listing_id: str,
    chat_id: str,
    message_id: int | None,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Повертає оголошення з ігнор-листа."""
    lang = user_svc.get_language(ctx.client, chat_id)

    db.remove_ignored(ctx.client, chat_id, listing_id)
    db.log_activity(
        ctx.client,
        chat_id,
        "unignore",
        {"listing_id": listing_id},
    )

    ctx.notifier.answer_callback(cb_id, T("ignored_removed", lang))


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


def _handle_buy(
    period: str,
    chat_id: str,
    cb_id: str,
    ctx: BotContext,
) -> None:
    """Обробляє натискання кнопки купівлі підписки.

    Args:
        period: 'monthly' або 'yearly'
        chat_id: ID чату
        cb_id: callback ID
        ctx: контекст бота
    """
    # 1. Перевірка періоду
    if period not in ("monthly", "yearly"):
        ctx.notifier.answer_callback(cb_id, "❌")
        return

    # 2. Ціни в Stars
    prices = {
        "monthly": 300,  # ⭐
        "yearly": 2000,  # ⭐
    }
    stars = prices[period]

    # 3. Payload (унікальний ID для обробки в successful_payment)
    payload = f"sub:{period}:{stars}"

    # 4. Назва та опис
    if period == "monthly":
        title = "RentAlert — 1 місяць"
        description = "Доступ до нових оголошень на 30 днів"
    else:
        title = "RentAlert — 12 місяців"
        description = "Доступ до нових оголошень на 365 днів (−17%)"

    # 5. Відповідаємо на callback (прибираємо «годинник»)
    ctx.notifier.answer_callback(cb_id)

    # 6. Надсилаємо invoice
    success = ctx.notifier.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        amount_stars=stars,
        label="Підписка RentAlert",
    )

    if not success:
        lang = user_svc.get_language(ctx.client, chat_id)
        ctx.notifier.send_message(
            chat_id,
            "❌ Не вдалось створити рахунок. Спробуйте пізніше.",
            keyboard=kb.main_menu_keyboard(lang),
        )
        return

    # 7. Логуємо спробу
    db.log_activity(
        ctx.client,
        chat_id,
        "buy_attempt",
        {"period": period, "stars": stars},
    )
