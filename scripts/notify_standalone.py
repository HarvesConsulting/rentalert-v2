"""Автономний notify для GitHub Actions.

Копія _notify_user з app.py, але без Flask-контексту.
"""

from __future__ import annotations

import logging
from typing import Any

from rentalert.catalog.catalog import Catalog
from rentalert.db.client import TursoClient
from rentalert.services import subscription as sub_svc
from rentalert.services import user as user_svc
from rentalert.services.market import get_deal_score
from rentalert.services.notifier import TelegramNotifier
from rentalert.translations import T

log = logging.getLogger(__name__)


def make_notify_fn(
    client: TursoClient,
    catalog: Catalog,
    notifier: TelegramNotifier,
):
    """Створює notify_fn для run_aggregation_cycle.

    Це замикання, яке використовує client/catalog/notifier.
    """

    def notify(chat_id: str, city_slug: str, listings: list[Any]) -> None:
        # ── Перевірка доступу ──
        status = sub_svc.get_access_status(client, chat_id)
        if not status["has_access"]:
            log.info(
                "⏭ Пропущено notify для %s (reason=%s)",
                chat_id,
                status.get("reason"),
            )
            return

        lang = user_svc.get_language(client, chat_id)
        city = catalog.city(city_slug)
        city_name = city.name if city else city_slug

        header = T("notification_header", lang, city=city_name, count=len(listings))
        notifier.send_message(chat_id, header)

        for i, lst in enumerate(listings[:5], 1):
            icon = lst.category_icon or "🏠"
            price = lst.price or "—"
            title = (lst.title or "")[:100]
            location = lst.location or ""
            link = lst.link or ""
            photo = lst.photo or ""

            lines = [f"{icon} <b>{i}. {price}</b>"]
            if lst.rooms:
                lines.append(f"🚪 {lst.rooms} кімн.")
            lines.append(title)
            if location:
                lines.append(f"📌 {location}")

            # Deal Score
            try:
                score = get_deal_score(
                    client,
                    city_slug=lst.city_slug,
                    location=lst.location,
                    category=lst.category,
                    rooms=lst.rooms,
                    price_str=lst.price,
                    area_m2=lst.area_m2,
                )
                if score is not None:
                    lines.append(f"{score.emoji} {score.label}")
            except Exception:
                pass

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

            notifier.send_photo_or_message(
                chat_id,
                photo,
                caption,
                keyboard=keyboard,
            )

        if len(listings) > 5:
            notifier.send_message(
                chat_id,
                T("notification_more", lang, count=len(listings) - 5),
            )

    return notify
