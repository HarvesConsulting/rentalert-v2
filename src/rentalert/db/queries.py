"""Високорівневі запити до Turso.

Усі функції приймають TursoClient першим аргументом.
Ніякого глобального стану.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from rentalert.db.client import TursoClient

log = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════
# User settings
# ═════════════════════════════════════════════════════════════


def ensure_user(client: TursoClient, chat_id: str) -> None:
    """Створює запис користувача, якщо його немає."""
    client.execute_non_query(
        "INSERT OR IGNORE INTO user_settings (chat_id) VALUES (?)",
        [chat_id],
    )


def touch_user(
    client: TursoClient,
    chat_id: str,
    *,
    username: str = "",
    first_name: str = "",
) -> None:
    """Оновлює last_seen, username, first_name, message_count."""
    ensure_user(client, chat_id)
    client.execute_non_query(
        """
        UPDATE user_settings
        SET last_seen = CURRENT_TIMESTAMP,
            message_count = message_count + 1,
            username = ?,
            first_name = ?
        WHERE chat_id = ?
        """,
        [username, first_name, chat_id],
    )


def get_user(client: TursoClient, chat_id: str) -> dict[str, Any] | None:
    """Повертає dict з налаштуваннями або None."""
    rows = client.execute(
        """
        SELECT chat_id, country, language, is_premium, premium_until,
               username, first_name, first_seen, last_seen, message_count
        FROM user_settings
        WHERE chat_id = ?
        """,
        [chat_id],
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "chat_id": r[0],
        "country": r[1] or "ua",
        "language": r[2] or "uk",
        "is_premium": bool(r[3]),
        "premium_until": r[4],
        "username": r[5] or "",
        "first_name": r[6] or "",
        "first_seen": r[7],
        "last_seen": r[8],
        "message_count": int(r[9] or 0),
    }


def get_user_country(client: TursoClient, chat_id: str) -> str:
    """Країна користувача (default 'ua')."""
    rows = client.execute(
        "SELECT country FROM user_settings WHERE chat_id = ?",
        [chat_id],
    )
    if not rows or not rows[0][0]:
        return "ua"
    return str(rows[0][0])


def get_user_language(client: TursoClient, chat_id: str) -> str:
    """Мова користувача (default 'uk')."""
    rows = client.execute(
        "SELECT language FROM user_settings WHERE chat_id = ?",
        [chat_id],
    )
    if not rows or not rows[0][0]:
        return "uk"
    return str(rows[0][0])


def set_user_country(client: TursoClient, chat_id: str, country: str) -> None:
    """Зберігає країну."""
    ensure_user(client, chat_id)
    client.execute_non_query(
        """
        UPDATE user_settings
        SET country = ?, updated_at = CURRENT_TIMESTAMP
        WHERE chat_id = ?
        """,
        [country, chat_id],
    )


def set_user_language(client: TursoClient, chat_id: str, language: str) -> None:
    """Зберігає мову."""
    ensure_user(client, chat_id)
    client.execute_non_query(
        """
        UPDATE user_settings
        SET language = ?, updated_at = CURRENT_TIMESTAMP
        WHERE chat_id = ?
        """,
        [language, chat_id],
    )


def is_premium(client: TursoClient, chat_id: str) -> bool:
    """Перевіряє, чи активний premium."""
    rows = client.execute(
        "SELECT is_premium, premium_until FROM user_settings WHERE chat_id = ?",
        [chat_id],
    )
    if not rows:
        return False
    flag, until = rows[0]
    if not flag:
        return False
    if not until:
        return True
    try:
        dt = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
        return dt > datetime.now(UTC)
    except Exception:
        return False


# ═════════════════════════════════════════════════════════════
# User cities
# ═════════════════════════════════════════════════════════════


def add_user_city(client: TursoClient, chat_id: str, city_slug: str) -> None:
    """Додає місто до підписок."""
    client.execute_non_query(
        "INSERT OR IGNORE INTO user_cities (chat_id, city_slug) VALUES (?, ?)",
        [chat_id, city_slug],
    )


def remove_user_city(client: TursoClient, chat_id: str, city_slug: str) -> None:
    """Видаляє місто."""
    client.execute_non_query(
        "DELETE FROM user_cities WHERE chat_id = ? AND city_slug = ?",
        [chat_id, city_slug],
    )


def clear_user_cities(client: TursoClient, chat_id: str) -> None:
    """Видаляє всі міста користувача."""
    client.execute_non_query(
        "DELETE FROM user_cities WHERE chat_id = ?",
        [chat_id],
    )


def get_user_cities(client: TursoClient, chat_id: str) -> list[str]:
    """Міста користувача в порядку додавання."""
    rows = client.execute(
        "SELECT city_slug FROM user_cities WHERE chat_id = ? ORDER BY added_at",
        [chat_id],
    )
    return [str(r[0]) for r in rows]


def get_all_user_cities(client: TursoClient) -> dict[str, list[str]]:
    """Усі підписки: {chat_id: [city_slug, ...]}."""
    rows = client.execute("SELECT chat_id, city_slug FROM user_cities")
    result: dict[str, list[str]] = {}
    for chat_id, slug in rows:
        result.setdefault(str(chat_id), []).append(str(slug))
    return result

def get_distinct_city_slugs(client: TursoClient) -> list[str]:
    """Унікальні міста, на які хтось підписаний.

    Використовується для парсингу: не треба парсити Київ 500 разів,
    якщо на нього підписані 500 користувачів.
    """
    rows = client.execute(
        "SELECT DISTINCT city_slug FROM user_cities ORDER BY city_slug"
    )
    return [str(r[0]) for r in rows]


# ═════════════════════════════════════════════════════════════
# User disabled sources (blacklist)
# ═════════════════════════════════════════════════════════════


def disable_source(client: TursoClient, chat_id: str, source_key: str) -> None:
    """Додає джерело в blacklist."""
    client.execute_non_query(
        """
        INSERT OR IGNORE INTO user_disabled_sources (chat_id, source_key)
        VALUES (?, ?)
        """,
        [chat_id, source_key],
    )


def enable_source(client: TursoClient, chat_id: str, source_key: str) -> None:
    """Видаляє джерело з blacklist."""
    client.execute_non_query(
        "DELETE FROM user_disabled_sources WHERE chat_id = ? AND source_key = ?",
        [chat_id, source_key],
    )


def get_disabled_sources(client: TursoClient, chat_id: str) -> set[str]:
    """Множина вимкнених джерел."""
    rows = client.execute(
        "SELECT source_key FROM user_disabled_sources WHERE chat_id = ?",
        [chat_id],
    )
    return {str(r[0]) for r in rows}


def clear_disabled_sources(client: TursoClient, chat_id: str) -> None:
    """Очищає blacklist."""
    client.execute_non_query(
        "DELETE FROM user_disabled_sources WHERE chat_id = ?",
        [chat_id],
    )


# ═════════════════════════════════════════════════════════════
# Seen listings
# ═════════════════════════════════════════════════════════════


def is_seen(client: TursoClient, listing_id: str) -> bool:
    """Чи оголошення вже бачили."""
    rows = client.execute(
        "SELECT 1 FROM seen_listings WHERE id = ?",
        [listing_id],
    )
    return bool(rows)


def get_seen_ids(
    client: TursoClient,
    listing_ids: list[str],
) -> set[str]:
    """Масово: множина ID, які вже в БД (по 500 за раз)."""
    if not listing_ids:
        return set()

    result: set[str] = set()
    chunk = 500

    for i in range(0, len(listing_ids), chunk):
        part = listing_ids[i : i + chunk]
        placeholders = ",".join("?" * len(part))
        rows = client.execute(
            f"SELECT id FROM seen_listings WHERE id IN ({placeholders})",
            list(part),
        )
        result.update(str(r[0]) for r in rows)

    return result


def save_listing(
    client: TursoClient,
    *,
    id: str,
    source_key: str,
    city_slug: str,
    title: str,
    price: str = "",
    location: str = "",
    link: str = "",
    photo: str = "",
    rooms: str | None = None,
    category: str = "",
    category_icon: str = "🏠",
    category_label: str = "",
    created_at: str | None = None,
) -> int:
    """Зберігає оголошення. Повертає affected count (1 = новий, 0 = вже був)."""
    return client.execute_non_query(
        """
        INSERT OR IGNORE INTO seen_listings
            (id, source_key, city_slug, title, price, location, link, photo,
             rooms, category, category_icon, category_label, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            id,
            source_key,
            city_slug,
            title,
            price,
            location,
            link,
            photo,
            rooms,
            category,
            category_icon,
            category_label,
            created_at,
        ],
    )


def get_listing(
    client: TursoClient,
    listing_id: str,
) -> dict[str, Any] | None:
    """Повертає оголошення з seen_listings за id, або None."""
    rows = client.execute(
        """
        SELECT id, source_key, city_slug, title, price, location, link,
               photo, rooms, category, category_icon, category_label, created_at
        FROM seen_listings
        WHERE id = ?
        """,
        [listing_id],
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r[0],
        "source_key": r[1],
        "city_slug": r[2],
        "title": r[3] or "",
        "price": r[4] or "",
        "location": r[5] or "",
        "link": r[6] or "",
        "photo": r[7] or "",
        "rooms": r[8],
        "category": r[9] or "",
        "category_icon": r[10] or "🏠",
        "category_label": r[11] or "",
        "created_at": r[12],
    }


def clear_seen_listings(client: TursoClient) -> int:
    """Видаляє ВСІ оголошення (для тестів)."""
    return client.execute_non_query("DELETE FROM seen_listings")


# ═════════════════════════════════════════════════════════════
# Fingerprint (для ігнорування)
# ═════════════════════════════════════════════════════════════


def make_fingerprint(title: str | None, location: str | None) -> str:
    """Стабільний хеш оголошення.

    Використовується для перехоплення перевипусків:
    продавець перевипустив оголошення з тим самим title + location —
    але новий ID → fingerprint той самий → не приходить.
    """
    key = f"{(title or '').lower().strip()}|{(location or '').lower().strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# ═════════════════════════════════════════════════════════════
# User categories
# ═════════════════════════════════════════════════════════════


def get_user_categories(
    client: TursoClient,
    chat_id: str,
) -> set[str]:
    """Категорії користувача (порожньо = усе увімкнено)."""
    rows = client.execute(
        "SELECT category_key FROM user_categories WHERE chat_id = ?",
        [chat_id],
    )
    return {str(r[0]) for r in rows}

def get_all_user_categories(
    client: TursoClient,
) -> dict[str, set[str]]:
    """Усі категорії всіх користувачів одним запитом.

    Returns:
        {chat_id: {category_key, ...}}

    Якщо у користувача порожній set — це означає
    «усе увімкнено» (як у поточній логіці user_svc.get_categories).
    """
    rows = client.execute(
        "SELECT chat_id, category_key FROM user_categories"
    )
    result: dict[str, set[str]] = {}
    for chat_id, cat_key in rows:
        result.setdefault(str(chat_id), set()).add(str(cat_key))
    return result


def set_user_categories(
    client: TursoClient,
    chat_id: str,
    category_keys: set[str],
) -> None:
    """Замінює всі категорії."""
    client.execute_non_query(
        "DELETE FROM user_categories WHERE chat_id = ?",
        [chat_id],
    )
    for key in category_keys:
        client.execute_non_query(
            "INSERT OR IGNORE INTO user_categories (chat_id, category_key) VALUES (?, ?)",
            [chat_id, key],
        )


# ═════════════════════════════════════════════════════════════
# User ignored (blacklist оголошень)
# ═════════════════════════════════════════════════════════════


def add_ignored(
    client: TursoClient,
    chat_id: str,
    listing_id: str,
    fingerprint: str,
) -> None:
    """Додає оголошення в чорний список користувача."""
    client.execute_non_query(
        """
        INSERT OR REPLACE INTO user_ignored (chat_id, listing_id, fingerprint)
        VALUES (?, ?, ?)
        """,
        [chat_id, listing_id, fingerprint],
    )


def remove_ignored(
    client: TursoClient,
    chat_id: str,
    listing_id: str,
) -> None:
    """Прибирає оголошення з чорного списку."""
    client.execute_non_query(
        "DELETE FROM user_ignored WHERE chat_id = ? AND listing_id = ?",
        [chat_id, listing_id],
    )


def clear_ignored(client: TursoClient, chat_id: str) -> None:
    """Очищає весь чорний список користувача."""
    client.execute_non_query(
        "DELETE FROM user_ignored WHERE chat_id = ?",
        [chat_id],
    )


def is_ignored(
    client: TursoClient,
    chat_id: str,
    listing_id: str,
    fingerprint: str | None = None,
) -> bool:
    """Перевіряє, чи ігнорується оголошення.

    Перевіряє за ID АБО (якщо вказано) за fingerprint.
    """
    if fingerprint:
        rows = client.execute(
            """
            SELECT 1 FROM user_ignored
            WHERE chat_id = ?
              AND (listing_id = ? OR fingerprint = ?)
            LIMIT 1
            """,
            [chat_id, listing_id, fingerprint],
        )
    else:
        rows = client.execute(
            "SELECT 1 FROM user_ignored WHERE chat_id = ? AND listing_id = ?",
            [chat_id, listing_id],
        )
    return bool(rows)


def get_ignored_ids(
    client: TursoClient,
    chat_id: str,
    listing_ids: list[str],
    fingerprints: list[str] | None = None,
) -> set[str]:
    """Повертає set ID (з переданих), які ігноруються за ID або fingerprint.

    Args:
        listing_ids: id оголошень, які треба перевірити.
        fingerprints: паралельний список (тієї ж довжини) або None.
    """
    if not listing_ids:
        return set()

    result: set[str] = set()
    chunk = 500

    # 1. За ID — тут усе ок
    for i in range(0, len(listing_ids), chunk):
        part = listing_ids[i : i + chunk]
        placeholders = ",".join("?" * len(part))
        rows = client.execute(
            f"""
            SELECT listing_id FROM user_ignored
            WHERE chat_id = ? AND listing_id IN ({placeholders})
            """,
            [chat_id, *part],
        )
        result.update(str(r[0]) for r in rows)

    # 2. За fingerprint — мапимо локально, щоб повернути САМЕ ті id, що передані
    if fingerprints and len(fingerprints) == len(listing_ids):
        fp_to_ids: dict[str, list[str]] = {}
        for lid, fp in zip(listing_ids, fingerprints, strict=False):
            fp_to_ids.setdefault(fp, []).append(lid)

        unique_fps = list(fp_to_ids.keys())
        for i in range(0, len(unique_fps), chunk):
            part = unique_fps[i : i + chunk]
            placeholders = ",".join("?" * len(part))
            rows = client.execute(
                f"""
                SELECT fingerprint FROM user_ignored
                WHERE chat_id = ? AND fingerprint IN ({placeholders})
                """,
                [chat_id, *part],
            )
            for r in rows:
                fp = str(r[0])
                result.update(fp_to_ids.get(fp, []))

    return result


def get_ignored_list(
    client: TursoClient,
    chat_id: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Список ігнорованих оголошень користувача (для /ignored)."""
    rows = client.execute(
        """
        SELECT i.listing_id, i.fingerprint, i.ignored_at,
               l.title, l.price, l.location, l.link
        FROM user_ignored i
        LEFT JOIN seen_listings l ON i.listing_id = l.id
        WHERE i.chat_id = ?
        ORDER BY i.ignored_at DESC
        LIMIT ?
        """,
        [chat_id, limit],
    )
    result: list[dict[str, Any]] = []
    for r in rows or []:
        result.append(
            {
                "id": r[0],
                "fingerprint": r[1],
                "ignored_at": r[2],
                "title": r[3] or "",
                "price": r[4] or "",
                "location": r[5] or "",
                "link": r[6] or "",
            }
        )
    return result


def count_ignored(client: TursoClient, chat_id: str) -> int:
    """Кількість ігнорованих оголошень."""
    rows = client.execute(
        "SELECT COUNT(*) FROM user_ignored WHERE chat_id = ?",
        [chat_id],
    )
    if not rows:
        return 0
    return int(rows[0][0] or 0)


# ═════════════════════════════════════════════════════════════
# Favorites
# ═════════════════════════════════════════════════════════════


def add_favorite(client: TursoClient, chat_id: str, listing_id: str) -> None:
    """Додає в обране."""
    client.execute_non_query(
        """
        INSERT OR IGNORE INTO user_favorites (chat_id, listing_id)
        VALUES (?, ?)
        """,
        [chat_id, listing_id],
    )


def remove_favorite(client: TursoClient, chat_id: str, listing_id: str) -> None:
    """Видаляє з обраного."""
    client.execute_non_query(
        "DELETE FROM user_favorites WHERE chat_id = ? AND listing_id = ?",
        [chat_id, listing_id],
    )


def is_favorite(client: TursoClient, chat_id: str, listing_id: str) -> bool:
    """Чи в обраному."""
    rows = client.execute(
        "SELECT 1 FROM user_favorites WHERE chat_id = ? AND listing_id = ?",
        [chat_id, listing_id],
    )
    return bool(rows)


def get_favorites(
    client: TursoClient,
    chat_id: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Останні обрані оголошення з деталями."""
    rows = client.execute(
        """
        SELECT f.listing_id, l.title, l.price, l.location, l.link,
               l.photo, l.category_icon, l.category_label, f.saved_at
        FROM user_favorites f
        LEFT JOIN seen_listings l ON f.listing_id = l.id
        WHERE f.chat_id = ?
        ORDER BY f.saved_at DESC
        LIMIT ?
        """,
        [chat_id, limit],
    )
    result: list[dict[str, Any]] = []
    for r in rows:
        result.append(
            {
                "id": r[0],
                "title": r[1] or "",
                "price": r[2] or "",
                "location": r[3] or "",
                "link": r[4] or "",
                "photo": r[5] or "",
                "category_icon": r[6] or "🏠",
                "category_label": r[7] or "",
                "saved_at": r[8],
            }
        )
    return result


def clear_favorites(client: TursoClient, chat_id: str) -> None:
    """Видаляє усі обрані."""
    client.execute_non_query(
        "DELETE FROM user_favorites WHERE chat_id = ?",
        [chat_id],
    )


def count_favorites(client: TursoClient, chat_id: str) -> int:
    """Кількість обраних."""
    rows = client.execute(
        "SELECT COUNT(*) FROM user_favorites WHERE chat_id = ?",
        [chat_id],
    )
    if not rows:
        return 0
    return int(rows[0][0] or 0)


# ═════════════════════════════════════════════════════════════
# Activity log
# ═════════════════════════════════════════════════════════════


def log_activity(
    client: TursoClient,
    chat_id: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Логує дію користувача."""
    details_json = json.dumps(details, ensure_ascii=False) if details else None
    client.execute_non_query(
        "INSERT INTO user_activity (chat_id, action, details) VALUES (?, ?, ?)",
        [chat_id, action, details_json],
    )
