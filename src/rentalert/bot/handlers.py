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
from rentalert.services import subscription as sub_svc
from rentalert.services.notifier import TelegramNotifier
from rentalert.translations import T

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Прапори країн
# ─────────────────────────────────────────────────────────────

_COUNTRY_FLAGS: dict[str, str] = {
    "ua": "🇺🇦",
    "pl": "🇵🇱",
    "pt": "🇵🇹",
    "ro": "🇷🇴",
    "bg": "🇧🇬",
    "de": "🇩🇪",
    "es": "🇪🇸",
    "hr": "🇭🇷",
}


def _country_flag(code: str) -> str:
    """Повертає прапор для коду країни (або 🌍, якщо невідомо)."""
    return _COUNTRY_FLAGS.get(code, "🌍")


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

    # 1. Даємо trial, якщо ще немає
    sub_svc.ensure_trial(ctx.client, chat_id)

    user = db.get_user(ctx.client, chat_id)
    if user is None or not user.get("first_seen"):
        _send_country_selector(chat_id, ctx)
    else:
        _send_main_menu(chat_id, ctx)

    # 2. Інформуємо, якщо trial/premium закінчився
    _maybe_warn_about_expired_access(chat_id, ctx)
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

    if text.startswith("/ignored"):
        _send_ignored(chat_id, ctx)
        return

    if text.startswith("/clear_ignored"):
        _clear_ignored(chat_id, ctx)
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

    if text == T("btn_my_subscriptions", "uk") or text == T("btn_my_subscriptions", "en"):
        _send_subscriptions_menu(chat_id, ctx)
        return True

    if text == T("btn_add_city", "uk") or text == T("btn_add_city", "en"):
        _send_add_city_prompt(chat_id, ctx)
        return True

    if text == T("btn_country_menu", "uk") or text == T("btn_country_menu", "en"):
        _send_country_selector(chat_id, ctx)
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
    for key in (
        "btn_my_subscriptions",
        "btn_add_city",
        "btn_country_menu",
        "btn_settings",
        "btn_help",
    ):
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
    flag = _country_flag(country)

    ctx.notifier.send_message(
        chat_id,
        T("main_menu", lang, country=country_label, flag=flag),
        keyboard=kb.main_menu_keyboard(lang),
    )


def _send_subscriptions_menu(chat_id: str, ctx: BotContext) -> None:
    """Показує inline-меню «Мої підписки»."""
    lang = user_svc.get_language(ctx.client, chat_id)
    ctx.notifier.send_message(
        chat_id,
        T("subscriptions_menu_title", lang),
        keyboard=kb.subscriptions_menu_keyboard(lang),
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


def _send_ignored(chat_id: str, ctx: BotContext) -> None:
    """Показує список ігнорованих оголошень з кнопками «Повернути»."""
    lang = user_svc.get_language(ctx.client, chat_id)
    rows = db.get_ignored_list(ctx.client, chat_id, limit=20)

    if not rows:
        _send_main_menu_with_text(chat_id, ctx, T("ignored_empty", lang))
        return

    lines = [T("ignored_title", lang, count=len(rows)), ""]
    buttons: list[list[dict[str, str]]] = []

    for r in rows:
        price = r.get("price") or "—"
        title = (r.get("title") or "—")[:60]
        lines.append(f"• <b>{price}</b> — {title}")
        buttons.append(
            [
                {
                    "text": f"↩️ {title[:30]}",
                    "callback_data": f"unign:{r['id']}",
                }
            ]
        )

    buttons.append(
        [
            {
                "text": T("btn_clear_ignored", lang),
                "callback_data": "clear_ignored:yes",
            }
        ]
    )

    ctx.notifier.send_message(
        chat_id,
        "\n".join(lines),
        keyboard={"inline_keyboard": buttons},
    )


def _clear_ignored(chat_id: str, ctx: BotContext) -> None:
    """Очищає весь ігнор-лист."""
    lang = user_svc.get_language(ctx.client, chat_id)
    n = db.count_ignored(ctx.client, chat_id)
    db.clear_ignored(ctx.client, chat_id)
    db.log_activity(ctx.client, chat_id, "clear_ignored", {"count": n})

    _send_main_menu_with_text(
        chat_id,
        ctx,
        T("ignored_cleared", lang, count=n),
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

def _maybe_warn_about_expired_access(chat_id: str, ctx: BotContext) -> None:
    """Показує попередження, якщо trial/premium закінчився."""
    status = sub_svc.get_access_status(ctx.client, chat_id)
    if status["has_access"]:
        return

    lang = user_svc.get_language(ctx.client, chat_id)
    reason = status.get("reason")

    if reason == "trial_expired":
        ctx.notifier.send_message(
            chat_id,
            T("access_trial_expired", lang),
        )
    elif reason == "no_user":
        return


def _send_subscription_status(chat_id: str, ctx: BotContext) -> None:
    """Показує статус підписки."""
    lang = user_svc.get_language(ctx.client, chat_id)
    status = sub_svc.get_access_status(ctx.client, chat_id)
    reason = status.get("reason")

    if reason == "free_country":
        text = T("subscription_free_ua", lang)
        buttons = None
    elif reason == "premium":
        text = T(
            "subscription_premium",
            lang,
            until=_format_date(status["until"]),
            days=status["days_left"] or 0,
        )
        buttons = _subscription_buttons(lang)
    elif reason == "trial":
        text = T(
            "subscription_trial",
            lang,
            until=_format_date(status["until"]),
            days=status["days_left"] or 0,
        )
        buttons = _subscription_buttons(lang)
    else:  # trial_expired
        text = T("subscription_expired", lang)
        buttons = _subscription_buttons(lang)

    keyboard = {"inline_keyboard": buttons} if buttons else None
    ctx.notifier.send_message(chat_id, text, keyboard=keyboard)


def _subscription_buttons(lang: str) -> list[list[dict[str, str]]]:
    """Кнопки купівлі підписки."""
    return [
        [
            {
                "text": T("subscription_buy_monthly", lang),
                "callback_data": "buy:monthly",
            }
        ],
        [
            {
                "text": T("subscription_buy_yearly", lang),
                "callback_data": "buy:yearly",
            }
        ],
    ]


def _format_date(iso: str | None) -> str:
    """Форматує ISO-дату як '03.10.2026'."""
    if not iso:
        return "—"
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return "—"
    
def handle_successful_payment(
    chat_id: str,
    payment: dict[str, Any],
    ctx: BotContext,
) -> None:
    """Обробляє успішну оплату від Telegram.

    Args:
        chat_id: ID чату
        payment: dict з successful_payment
        ctx: контекст бота
    """
    import json

    from rentalert.services import subscription as sub_svc

    # 1. Розбираємо payload
    # Формат: "sub:monthly:300" або "sub:yearly:2000"
    payload = payment.get("invoice_payload", "")
    parts = payload.split(":")
    period = parts[1] if len(parts) > 1 else "monthly"
    stars = int(parts[2]) if len(parts) > 2 else 0

    # Тривалість
    days = 365 if period == "yearly" else 30

    # 2. Зберігаємо платіж у БД
    db.save_payment(
        ctx.client,
        id=payment.get("telegram_payment_charge_id", ""),
        chat_id=chat_id,
        amount_stars=stars,
        kind="subscription",
        period=period,
        days=days,
        raw_payload=json.dumps(payment, ensure_ascii=False),
    )

    # 3. Продовжуємо premium
    new_until_iso = sub_svc.extend_premium(ctx.client, chat_id, days)

    # 4. Логуємо
    db.log_activity(
        ctx.client,
        chat_id,
        "payment_success",
        {"period": period, "days": days, "stars": stars},
    )

    # 5. Форматуємо дату
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(new_until_iso.replace("Z", "+00:00"))
        date_str = dt.strftime("%d.%m.%Y")
    except Exception:
        date_str = new_until_iso

    # 6. Надсилаємо підтвердження
    lang = user_svc.get_language(ctx.client, chat_id)
    period_label = "рік" if period == "yearly" else "місяць"
    ctx.notifier.send_message(
        chat_id,
        f"✅ <b>Оплата успішна!</b>\n\n"
        f"💎 <b>{stars} ⭐</b> ({period_label})\n"
        f"📅 Підписка активна до <b>{date_str}</b>\n\n"
        f"Дякуємо за підтримку! 🎉",
        keyboard=kb.main_menu_keyboard(lang),
    )

    # 7. Реферальний бонус
    _handle_referral_bonus(chat_id, ctx)


def _handle_referral_bonus(chat_id: str, ctx: BotContext) -> None:
    """Дає бонус тому, хто запросив користувача."""
    from rentalert.services import subscription as sub_svc

    user = db.get_user(ctx.client, chat_id)
    if not user:
        return

    referrer_id = user.get("referred_by")
    if not referrer_id:
        return

    # Збільшуємо лічильник
    count = db.increment_referrals(ctx.client, referrer_id)
    log.info("👥 Реферал: %s → %s (всього: %d)", chat_id, referrer_id, count)

    # Кожні 3 → +30 днів
    if count % 3 == 0:
        sub_svc.extend_premium(ctx.client, referrer_id, 30)

        try:
            ctx.notifier.send_message(
                referrer_id,
                f"🎉 <b>Бонус за друзів!</b>\n\n"
                f"Ви запросили {count} друзів — і отримали "
                f"<b>+30 днів</b> безкоштовно!\n\n"
                f"Запрошуйте ще! 🚀",
            )
        except Exception as e:
            log.exception("Referral notify failed: %s", e)
