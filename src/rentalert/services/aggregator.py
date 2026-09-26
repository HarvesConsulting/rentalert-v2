"""Головний цикл агрегації.

Збирає нові оголошення з усіх джерел для всіх підписок,
дедуплікує через seen_listings, розсилає сповіщення.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rentalert.catalog.catalog import Catalog
from rentalert.catalog.models import City
from rentalert.db import queries as db
from rentalert.db.client import TursoClient
from rentalert.parsers.base import Listing
from rentalert.parsers.registry import PARSER_REGISTRY

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Налаштування
# ─────────────────────────────────────────────────────────────

RECENT_HOURS = 6
"""Скільки годин вважати «свіжим» оголошенням."""


# ─────────────────────────────────────────────────────────────
# Типи
# ─────────────────────────────────────────────────────────────

NotifyFn = Callable[[str, str, list[Listing]], None]
"""Callback для розсилки: (chat_id, city_slug, listings)."""


@dataclass
class AggregationStats:
    """Результати одного циклу агрегації."""

    pairs_checked: int = 0
    listings_fetched: int = 0
    listings_new: int = 0
    users_notified: int = 0
    errors: int = 0


# ─────────────────────────────────────────────────────────────
# Головна функція
# ─────────────────────────────────────────────────────────────


def run_aggregation_cycle(
    catalog: Catalog,
    client: TursoClient,
    notify_fn: NotifyFn,
    *,
    recent_hours: int = RECENT_HOURS,
) -> AggregationStats:
    """Один цикл агрегації.

    Args:
        catalog: завантажений каталог
        client: Turso-клієнт
        notify_fn: callback (chat_id, city_slug, listings)
        recent_hours: вікно свіжості

    Returns:
        Статистика циклу.
    """
    stats = AggregationStats()

    # 1. Отримуємо всі підписки
    all_subs = db.get_all_user_cities(client)
    if not all_subs:
        log.info("Немає підписок — цикл пропущено")
        return stats

    # 2. Унікальні пари (city_slug, source_key)
    pairs: set[tuple[str, str]] = set()
    for _chat_id, cities in all_subs.items():
        for city_slug in cities:
            city = catalog.city(city_slug)
            if city is None:
                log.warning("Місто %r не знайдено в каталозі", city_slug)
                continue
            for source_key in city.refs:
                pairs.add((city_slug, source_key))

    if not pairs:
        log.info("Немає пар для перевірки")
        return stats

    log.info("Цикл агрегації: %d пар (місто × джерело)", len(pairs))

    # 3. Парсимо кожну пару
    fresh_by_pair: dict[tuple[str, str], list[Listing]] = {}
    cutoff = datetime.now(UTC) - timedelta(hours=recent_hours)

    for city_slug, source_key in pairs:
        stats.pairs_checked += 1

        city = catalog.city(city_slug)
        parser = PARSER_REGISTRY.get(source_key)
        if city is None or parser is None:
            continue

        try:
            listings = _fetch_and_save(
                parser=parser,
                city=city,
                source_key=source_key,
                client=client,
                cutoff=cutoff,
            )
        except Exception as e:
            log.exception("Помилка fetch %s/%s: %s", city_slug, source_key, e)
            stats.errors += 1
            continue

        stats.listings_fetched += len(listings)
        stats.listings_new += len(listings)

        if listings:
            fresh_by_pair[(city_slug, source_key)] = listings
            log.info("  + %s/%s: %d нових", city_slug, source_key, len(listings))

# 4. Розсилаємо
    #    Одним запитом — disabled sources для всіх
    #    Одним запитом — enabled categories для всіх
    all_categories = db.get_all_user_categories(client)

    for chat_id, cities in all_subs.items():
        disabled = db.get_disabled_sources(client, chat_id)
        enabled_categories = all_categories.get(str(chat_id), set())

        for city_slug in cities:
            raw_to_send = _collect_for_user(
                city_slug=city_slug,
                disabled=disabled,
                enabled_categories=enabled_categories,
                catalog=catalog,
                fresh_by_pair=fresh_by_pair,
                ignored_ids=set(),
            )

            if not raw_to_send:
                continue

            # Фільтруємо ігноровані
            listing_ids = [lst.id for lst in raw_to_send]
            fingerprints = [db.make_fingerprint(lst.title, lst.location) for lst in raw_to_send]
            ignored_ids = db.get_ignored_ids(client, chat_id, listing_ids, fingerprints)

            to_send = [lst for lst in raw_to_send if lst.id not in ignored_ids]

            if to_send:
                try:
                    notify_fn(chat_id, city_slug, to_send)
                    stats.users_notified += 1
                except Exception as e:
                    log.exception("Notify помилка для %s: %s", chat_id, e)
                    stats.errors += 1

    log.info(
        "Цикл завершено: %d пар, %d нових, %d користувачів сповіщено",
        stats.pairs_checked,
        stats.listings_new,
        stats.users_notified,
    )
    return stats


def fetch_city_now(
    catalog: Catalog,
    client: TursoClient,
    city_slug: str,
) -> list[Listing]:
    """Парсить одне місто ЗАРАЗ і повертає свіжі оголошення.

    Використовується для "першого показу" після додавання міста.
    НЕ оновлює базову лінію — усе знайдене йде користувачу.

    Args:
        catalog: каталог
        client: Turso-клієнт
        city_slug: slug міста

    Returns:
        Список свіжих оголошень (з усіх джерел міста).
    """
    city = catalog.city(city_slug)
    if city is None:
        log.warning("fetch_city_now: місто %r не знайдено", city_slug)
        return []

    # Вікно свіжості — 7 днів (щоб показати хоч щось навіть у тихому місті)
    cutoff = datetime.now(UTC) - timedelta(days=7)

    all_listings: list[Listing] = []
    for source_key in city.refs:
        parser = PARSER_REGISTRY.get(source_key)
        if parser is None:
            continue

        try:
            listings = _fetch_and_save(
                parser=parser,
                city=city,
                source_key=source_key,
                client=client,
                cutoff=cutoff,
            )
            all_listings.extend(listings)
        except Exception as e:
            log.exception("fetch_city_now %s/%s: %s", city_slug, source_key, e)

    # Сортуємо за created_at (новіші — першими)
    all_listings.sort(
        key=lambda lst: lst.created_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    log.info(
        "fetch_city_now %s: %d оголошень",
        city_slug,
        len(all_listings),
    )
    return all_listings


# ─────────────────────────────────────────────────────────────
# Внутрішнє
# ─────────────────────────────────────────────────────────────


def _fetch_and_save(
    *,
    parser,
    city: City,
    source_key: str,
    client: TursoClient,
    cutoff: datetime,
) -> list[Listing]:
    """Парсить, дедуплікує, зберігає, повертає свіжі нові оголошення."""
    source = parser.source

    # Callback: чи ВСІ id з переданого списку вже в БД?
    def _is_all_seen(ids: list[str]) -> bool:
        if not ids:
            return False
        seen = db.get_seen_ids(client, ids)
        return len(seen) == len(ids)

    # Парсимо — seen_checker підтримують не всі парсери
    import inspect

    fetch_sig = inspect.signature(parser.fetch)
    if "seen_checker" in fetch_sig.parameters:
        listings = parser.fetch(
            city,
            list(source.categories),
            seen_checker=_is_all_seen,
        )
    else:
        listings = parser.fetch(city, list(source.categories))

    if not listings:
        return []

    # Дедуплікація
    ids = [lst.id for lst in listings]
    seen = db.get_seen_ids(client, ids)

    fresh: list[Listing] = []
    for lst in listings:
        if lst.id in seen:
            continue

        # Зберігаємо у БД
        db.save_listing(
            client,
            id=lst.id,
            source_key=lst.source_key,
            city_slug=lst.city_slug,
            title=lst.title,
            price=lst.price,
            location=lst.location,
            link=lst.link,
            photo=lst.photo,
            rooms=lst.rooms,
            category=lst.category,
            category_icon=lst.category_icon,
            category_label=lst.category_label,
            created_at=lst.created_at.isoformat() if lst.created_at else None,
        )

        # Фільтр свіжості
        if lst.created_at is None or lst.created_at >= cutoff:
            fresh.append(lst)

    return fresh


def _collect_for_user(
    *,
    city_slug: str,
    disabled: set[str],
    enabled_categories: set[str],
    catalog: Catalog,
    fresh_by_pair: dict[tuple[str, str], list[Listing]],
    ignored_ids: set[str],
) -> list[Listing]:
    """Збирає оголошення для користувача.

    Фільтри:
      - disabled: вимкнені джерела (source_key)
      - enabled_categories: якщо непорожній — тільки ці категорії.
        Порожній set = «усе увімкнено» (як у user_svc.get_categories).
      - ignored_ids: id оголошень, які користувач ігнорує
    """
    city = catalog.city(city_slug)
    if city is None:
        return []

    # Якщо set непорожній — фільтруємо. Якщо порожній — усе увімкнено.
    filter_categories = bool(enabled_categories)

    result: list[Listing] = []
    for source_key in city.refs:
        if source_key in disabled:
            continue
        for lst in fresh_by_pair.get((city_slug, source_key), []):
            if lst.id in ignored_ids:
                continue
            if filter_categories and lst.category not in enabled_categories:
                continue
            result.append(lst)
    return result
