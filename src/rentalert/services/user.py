"""Сервіс користувача — високорівнева логіка.

Об'єднує db/queries + catalog.
"""

from __future__ import annotations

import logging

from rentalert.catalog.catalog import Catalog
from rentalert.catalog.models import City, Source
from rentalert.db import queries as db
from rentalert.db.client import TursoClient

log = logging.getLogger(__name__)

DEFAULT_COUNTRY = "ua"
DEFAULT_LANGUAGE = "uk"


# ─────────────────────────────────────────────────────────────
# Користувач
# ─────────────────────────────────────────────────────────────

def ensure_user(
    client: TursoClient,
    chat_id: str,
    *,
    username: str = "",
    first_name: str = "",
) -> dict:
    """Створює або оновлює користувача. Повертає dict налаштувань."""
    db.ensure_user(client, chat_id)
    if username or first_name:
        db.touch_user(client, chat_id, username=username, first_name=first_name)

    user = db.get_user(client, chat_id)
    if user is None:
        # fallback (не має траплятись після ensure)
        return {
            "chat_id": chat_id,
            "country": DEFAULT_COUNTRY,
            "language": DEFAULT_LANGUAGE,
            "is_premium": False,
            "username": username,
            "first_name": first_name,
        }
    return user


def get_language(client: TursoClient, chat_id: str) -> str:
    """Мова користувача (default 'uk')."""
    return db.get_user_language(client, chat_id) or DEFAULT_LANGUAGE


def get_country(client: TursoClient, chat_id: str) -> str:
    """Країна користувача (default 'ua')."""
    return db.get_user_country(client, chat_id) or DEFAULT_COUNTRY


def set_language(client: TursoClient, chat_id: str, language: str) -> None:
    """Встановлює мову."""
    if language not in ("uk", "en"):
        raise ValueError(f"Непідтримувана мова: {language!r}")
    db.set_user_language(client, chat_id, language)


def set_country(client: TursoClient, chat_id: str, country: str) -> None:
    """Встановлює країну."""
    db.set_user_country(client, chat_id, country)


# ─────────────────────────────────────────────────────────────
# Міста користувача
# ─────────────────────────────────────────────────────────────

def get_city_slugs(client: TursoClient, chat_id: str) -> list[str]:
    """Slug міст користувача."""
    return db.get_user_cities(client, chat_id)


def get_cities(
    catalog: Catalog,
    client: TursoClient,
    chat_id: str,
) -> list[City]:
    """Об'єкти City з підписок користувача."""
    slugs = db.get_user_cities(client, chat_id)
    result: list[City] = []
    for slug in slugs:
        city = catalog.city(slug)
        if city:
            result.append(city)
        else:
            log.warning("Місто %r відсутнє в каталозі", slug)
    return result


def add_city(client: TursoClient, chat_id: str, city_slug: str) -> None:
    """Додає місто."""
    db.add_user_city(client, chat_id, city_slug)


def remove_city(client: TursoClient, chat_id: str, city_slug: str) -> None:
    """Видаляє місто."""
    db.remove_user_city(client, chat_id, city_slug)


# ─────────────────────────────────────────────────────────────
# Джерела (з урахуванням blacklist)
# ─────────────────────────────────────────────────────────────

def get_enabled_sources(
    catalog: Catalog,
    client: TursoClient,
    chat_id: str,
    city_slug: str,
) -> list[Source]:
    """Усі джерела міста, які користувач НЕ вимкнув.

    За замовчуванням — усі джерела міста увімкнені.
    """
    city = catalog.city(city_slug)
    if city is None:
        return []

    disabled = db.get_disabled_sources(client, chat_id)

    result: list[Source] = []
    for source_key in city.refs:
        if source_key in disabled:
            continue
        source = catalog.source(source_key)
        if source is None:
            log.warning("Джерело %r відсутнє в каталозі", source_key)
            continue
        result.append(source)
    return result


def get_all_sources_for_user(
    catalog: Catalog,
    client: TursoClient,
    chat_id: str,
) -> dict[str, list[Source]]:
    """Маппінг city_slug → [Source], які користувач отримує для кожного міста."""
    result: dict[str, list[Source]] = {}
    for city_slug in db.get_user_cities(client, chat_id):
        result[city_slug] = get_enabled_sources(catalog, client, chat_id, city_slug)
    return result


def is_source_enabled(
    client: TursoClient,
    chat_id: str,
    source_key: str,
) -> bool:
    """Чи увімкнено джерело (не в blacklist)."""
    disabled = db.get_disabled_sources(client, chat_id)
    return source_key not in disabled


def enable_source(
    client: TursoClient,
    chat_id: str,
    source_key: str,
) -> None:
    """Увімкнути джерело (видалити з blacklist)."""
    db.enable_source(client, chat_id, source_key)


def disable_source(
    client: TursoClient,
    chat_id: str,
    source_key: str,
) -> None:
    """Вимкнути джерело (додати в blacklist)."""
    db.disable_source(client, chat_id, source_key)


def toggle_source(
    client: TursoClient,
    chat_id: str,
    source_key: str,
) -> bool:
    """Перемикає джерело. Повертає новий стан (True = увімкнено)."""
    if is_source_enabled(client, chat_id, source_key):
        disable_source(client, chat_id, source_key)
        return False
    enable_source(client, chat_id, source_key)
    return True


def get_disabled_sources(
    client: TursoClient,
    chat_id: str,
) -> set[str]:
    """Вимкнені джерела."""
    return db.get_disabled_sources(client, chat_id)
