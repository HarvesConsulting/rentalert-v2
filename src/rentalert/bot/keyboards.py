"""Побудова клавіатур для Telegram.

Усі функції приймають дані + мову, повертають dict у форматі Telegram API.

Приклад використання:
    kb = main_menu_keyboard("uk")
    notifier.send_message(chat_id, "Hello", keyboard=kb)
"""

from __future__ import annotations

from typing import Any

from rentalert.catalog.catalog import Catalog
from rentalert.catalog.models import City, Source
from rentalert.translations import T

# ─────────────────────────────────────────────────────────────
# Reply-клавіатури (під полем вводу)
# ─────────────────────────────────────────────────────────────


def main_menu_keyboard(lang: str = "uk") -> dict[str, Any]:
    """Головне меню — 4 кнопки у 4 ряди."""
    return {
        "keyboard": [
            [{"text": T("btn_my_subscriptions", lang)}],
            [{"text": T("btn_add_city", lang)}],
            [{"text": T("btn_settings", lang)}],
            [{"text": T("btn_help", lang)}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }

def subscriptions_menu_keyboard(lang: str = "uk") -> dict[str, Any]:
    """Inline-меню «Мої підписки»: Мої міста / Обране / Ігноровані."""
    return {
        "inline_keyboard": [
            [
                {
                    "text": T("btn_my_cities", lang),
                    "callback_data": "subs:my_cities",
                }
            ],
            [
                {
                    "text": T("btn_favorites", lang),
                    "callback_data": "subs:favorites",
                }
            ],
            [
                {
                    "text": T("btn_ignored", lang),
                    "callback_data": "subs:ignored",
                }
            ],
        ]
    }

def remove_keyboard() -> dict[str, Any]:
    """Прибирає reply-клавіатуру."""
    return {"remove_keyboard": True}


# ─────────────────────────────────────────────────────────────
# Inline-клавіатури (під повідомленням)
# ─────────────────────────────────────────────────────────────


def country_selector_keyboard(
    countries: list[dict[str, Any]],
    current: str,
    lang: str = "uk",
) -> dict[str, Any]:
    """Меню вибору країни.

    Args:
        countries: список dict з 'code', 'name', 'free', 'price_stars'
        current: поточний код країни
        lang: мова
    """
    rows: list[list[dict[str, str]]] = []

    for c in countries:
        code = c["code"]
        name = c["name"]
        mark = "✅ " if code == current else ""

        if c.get("free"):
            suffix = "(free)" if lang == "en" else "(безкоштовно)"
        else:
            unit = "mo" if lang == "en" else "міс"
            suffix = f"({c['price_stars']} ⭐/{unit})"

        rows.append(
            [
                {
                    "text": f"{mark}{name} {suffix}",
                    "callback_data": f"country:{code}",
                }
            ]
        )

    return {"inline_keyboard": rows}


def city_search_results_keyboard(
    cities: list[City],
    user_city_slugs: set[str],
) -> dict[str, Any]:
    """Результати пошуку міст для додавання.

    Позначка ✅ якщо вже додано.
    """
    rows: list[list[dict[str, str]]] = []

    for c in cities:
        region = c.region
        label = c.name + (f" ({region})" if region else "")
        already = "✅ " if c.slug in user_city_slugs else "➕ "

        rows.append(
            [
                {
                    "text": f"{already}{label}"[:60],
                    "callback_data": f"add_city:{c.slug}",
                }
            ]
        )

    return {"inline_keyboard": rows}


def my_cities_keyboard(
    cities: list[City],
) -> dict[str, Any]:
    """Список міст користувача з кнопкою ❌ для видалення."""
    rows: list[list[dict[str, str]]] = []

    for c in cities:
        region = c.region
        label = c.name + (f" ({region})" if region else "")
        rows.append(
            [
                {
                    "text": f"❌ {label}"[:60],
                    "callback_data": f"remove_city:{c.slug}",
                }
            ]
        )

    return {"inline_keyboard": rows}


def categories_keyboard(
    catalog: Catalog,
    country: str,
    enabled: set[str],
    lang: str = "uk",
) -> dict[str, Any]:
    """Меню категорій для країни.

    Args:
        catalog: каталог (щоб витягнути категорії)
        country: код країни
        enabled: які категорії увімкнені
        lang: мова
    """
    # Категорії за країною
    country_categories = _categories_for_country(country)

    rows: list[list[dict[str, str]]] = []
    for cat_key, icon, label in country_categories:
        check = "✅" if cat_key in enabled else "⬜"
        rows.append(
            [
                {
                    "text": f"{check} {icon} {label}",
                    "callback_data": f"toggle_cat:{cat_key}",
                }
            ]
        )

    rows.append(
        [
            {
                "text": T("btn_save_categories", lang),
                "callback_data": "save_categories",
            }
        ]
    )

    return {"inline_keyboard": rows}


def sources_keyboard(
    sources: list[Source],
    enabled_keys: set[str],
    city_slug: str,
) -> dict[str, Any]:
    """Меню джерел для конкретного міста.

    Показуємо тільки ті, які підтримують місто.
    ✅ = увімкнено, ⬜ = вимкнено.
    """
    rows: list[list[dict[str, str]]] = []

    for s in sources:
        check = "✅" if s.key in enabled_keys else "⬜"
        rows.append(
            [
                {
                    "text": f"{check} {s.icon} {s.name}",
                    "callback_data": f"toggle_source:{city_slug}:{s.key}",
                }
            ]
        )

    return {"inline_keyboard": rows}


def language_keyboard(lang: str = "uk") -> dict[str, Any]:
    """Вибір мови."""
    return {
        "inline_keyboard": [
            [{"text": "🇺🇦 Українська", "callback_data": "lang:uk"}],
            [{"text": "🇬🇧 English", "callback_data": "lang:en"}],
        ]
    }


def confirm_keyboard(
    action: str,
    lang: str = "uk",
) -> dict[str, Any]:
    """Кнопки Так/Ні для підтвердження.

    Args:
        action: префікс callback, наприклад 'clear_cities'
    """
    yes = T("btn_yes", lang)
    no = T("btn_no", lang)
    return {
        "inline_keyboard": [
            [
                {"text": f"✅ {yes}", "callback_data": f"{action}:yes"},
                {"text": f"❌ {no}", "callback_data": f"{action}:no"},
            ]
        ]
    }


def favorite_button(
    listing_id: str,
    is_favorite: bool,
    lang: str = "uk",
) -> dict[str, Any]:
    """Кнопка «В обране» / «Видалити з обраного» для оголошення."""
    if is_favorite:
        text = T("btn_remove_favorite", lang)
        icon = "✅"
    else:
        text = T("btn_add_favorite", lang)
        icon = "⭐"

    return {
        "inline_keyboard": [
            [
                {
                    "text": f"{icon} {text}",
                    "callback_data": f"fav:{listing_id}",
                }
            ]
        ]
    }


def settings_keyboard(
    country_name: str,
    enabled_sources: int,
    total_sources: int,
    lang: str = "uk",
) -> dict[str, Any]:
    """Меню налаштувань."""
    return {
        "inline_keyboard": [
            [
                {
                    "text": T("btn_country", lang, country=country_name),
                    "callback_data": "cfg:country",
                }
            ],
            [
                {
                    "text": f"📡 {T('btn_sources', lang)} ({enabled_sources}/{total_sources})",
                    "callback_data": "cfg:sources",
                }
            ],
            [
                {
                    "text": T("btn_types", lang),
                    "callback_data": "cfg:types",
                }
            ],
            [
                {
                    "text": T("btn_language", lang),
                    "callback_data": "cfg:language",
                }
            ],
            [
                {
                    "text": T("btn_clear_cities", lang),
                    "callback_data": "cfg:clear_cities",
                }
            ],
        ]
    }


def help_keyboard(lang: str = "uk") -> dict[str, Any]:
    """Кнопки у довідці."""
    return {
        "inline_keyboard": [
            [{"text": T("btn_feedback", lang), "callback_data": "feedback"}],
            [{"text": T("btn_rate", lang), "callback_data": "rate"}],
        ]
    }


# ─────────────────────────────────────────────────────────────
# Внутрішнє
# ─────────────────────────────────────────────────────────────


def _categories_for_country(country: str) -> list[tuple[str, str, str]]:
    """Повертає список (cat_key, icon, label) для країни.

    Тимчасово захардкоджено. Пізніше — з catalog.
    """
    data: dict[str, list[tuple[str, str, str]]] = {
        "ua": [
            ("apartment", "🏢", "Квартири"),
            ("house", "🏠", "Будинки"),
            ("room", "🚪", "Кімнати"),
            ("daily", "🌙", "Подобова"),
        ],
        "pl": [
            ("apartment", "🏢", "Mieszkania"),
            ("house", "🏠", "Domy"),
            ("room", "🚪", "Pokoje"),
        ],
        "pt": [
            ("apartment", "🏢", "Apartamentos"),
            ("house", "🏠", "Moradias"),
            ("room", "🚪", "Quartos"),
        ],
        "ro": [
            ("apartment", "🏢", "Apartamente"),
            ("house", "🏠", "Case"),
        ],
        "bg": [
            ("apartment", "🏢", "Апартаменти"),
            ("house", "🏠", "Къщи"),
        ],
        "de": [
            ("apartment", "🏢", "Wohnungen"),
            ("house", "🏠", "Häuser"),
            ("room", "🚪", "WG-Zimmer"),
        ],
        "es": [
            ("apartment", "🏢", "Pisos"),
            ("house", "🏠", "Casas"),
            ("room", "🚪", "Habitaciones"),
        ],
        "hr": [
            ("apartment", "🏢", "Stanovi"),
            ("house", "🏠", "Kuće"),
            ("room", "🚪", "Sobe"),
        ],
    }
    return data.get(country, data["ua"])
