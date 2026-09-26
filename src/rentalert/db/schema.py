"""Схема БД Turso: CREATE TABLE + індекси.

Використовується при старті застосунку через init_schema(client).
"""

from __future__ import annotations

import logging

from rentalert.db.client import TursoClient

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# SQL-схема
# ─────────────────────────────────────────────────────────────

TABLES: list[str] = [
    # ─── Налаштування користувача ───
    """
    CREATE TABLE IF NOT EXISTS user_settings (
        chat_id         TEXT PRIMARY KEY,
        country         TEXT NOT NULL DEFAULT 'ua',
        language        TEXT NOT NULL DEFAULT 'uk',
        is_premium      INTEGER NOT NULL DEFAULT 0,
        premium_until   DATETIME,
        username        TEXT,
        first_name      TEXT,
        first_seen      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        message_count   INTEGER NOT NULL DEFAULT 0,
        created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        trial_ends_at    DATETIME,
        referred_by      TEXT,
        referrals_count  INTEGER NOT NULL DEFAULT 0
    )
    """,
    # ─── Підписки на міста ───
    """
    CREATE TABLE IF NOT EXISTS user_cities (
        chat_id     TEXT NOT NULL,
        city_slug   TEXT NOT NULL,
        added_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, city_slug)
    )
    """,
    # ─── Вимкнені джерела (blacklist) ───
    """
    CREATE TABLE IF NOT EXISTS user_disabled_sources (
        chat_id      TEXT NOT NULL,
        source_key   TEXT NOT NULL,
        disabled_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, source_key)
    )
    """,
    # ─── Переглянуті оголошення (для дедуплікації) ───
    """
    CREATE TABLE IF NOT EXISTS seen_listings (
        id              TEXT PRIMARY KEY,
        source_key      TEXT NOT NULL,
        city_slug       TEXT NOT NULL,
        title           TEXT NOT NULL,
        price           TEXT,
        location        TEXT,
        link            TEXT,
        photo           TEXT,
        rooms           TEXT,
        category        TEXT,
        category_icon   TEXT,
        category_label  TEXT,
        created_at      DATETIME,
        first_seen      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # ─── Обрані оголошення ───
    """
    CREATE TABLE IF NOT EXISTS user_favorites (
        chat_id      TEXT NOT NULL,
        listing_id   TEXT NOT NULL,
        saved_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, listing_id)
    )
    """,
    # ─── Категорії користувача ───
    """
    CREATE TABLE IF NOT EXISTS user_categories (
        chat_id      TEXT NOT NULL,
        category_key TEXT NOT NULL,
        PRIMARY KEY (chat_id, category_key)
    )
    """,
    # ─── Ігноровані оголошення ───
    """
    CREATE TABLE IF NOT EXISTS user_ignored (
        chat_id      TEXT NOT NULL,
        listing_id   TEXT NOT NULL,
        fingerprint  TEXT NOT NULL,
        ignored_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, listing_id)
    )
    """,
    # ─── Лог дій ───
    """
    CREATE TABLE IF NOT EXISTS user_activity (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id     TEXT NOT NULL,
        action      TEXT NOT NULL,
        details     TEXT,
        created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # ─── Платежі ───
    """
    CREATE TABLE IF NOT EXISTS payments (
        id            TEXT PRIMARY KEY,
        chat_id       TEXT NOT NULL,
        amount_stars  INTEGER NOT NULL,
        currency      TEXT NOT NULL DEFAULT 'XTR',
        kind          TEXT NOT NULL DEFAULT 'subscription',
        period        TEXT,
        days          INTEGER,
        country_code  TEXT,
        paid_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        raw_payload   TEXT
    )
    """,
]


INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_user_settings_country ON user_settings(country)",
    "CREATE INDEX IF NOT EXISTS idx_user_settings_last_seen ON user_settings(last_seen DESC)",
    "CREATE INDEX IF NOT EXISTS idx_user_cities_slug ON user_cities(city_slug)",
    "CREATE INDEX IF NOT EXISTS idx_disabled_sources_key ON user_disabled_sources(source_key)",
    "CREATE INDEX IF NOT EXISTS idx_seen_listings_city ON seen_listings(city_slug)",
    "CREATE INDEX IF NOT EXISTS idx_seen_listings_source ON seen_listings(source_key)",
    "CREATE INDEX IF NOT EXISTS idx_seen_listings_created ON seen_listings(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_seen_listings_first_seen ON seen_listings(first_seen DESC)",
    "CREATE INDEX IF NOT EXISTS idx_favorites_chat ON user_favorites(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_favorites_listing ON user_favorites(listing_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_categories_chat ON user_categories(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_ignored_fingerprint ON user_ignored(chat_id, fingerprint)",
    "CREATE INDEX IF NOT EXISTS idx_ignored_chat ON user_ignored(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_activity_chat ON user_activity(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_activity_action ON user_activity(action)",
    "CREATE INDEX IF NOT EXISTS idx_activity_created ON user_activity(created_at DESC)",
]

# ─────────────────────────────────────────────────────────────
# Міграції (для існуючих БД)
# ─────────────────────────────────────────────────────────────

MIGRATIONS: list[tuple[str, str, str]] = [
    # (table, column, type)
    ("user_settings", "trial_ends_at", "DATETIME"),
    ("user_settings", "referred_by", "TEXT"),
    ("user_settings", "referrals_count", "INTEGER DEFAULT 0"),
]

PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS payments (
    id            TEXT PRIMARY KEY,
    chat_id       TEXT NOT NULL,
    amount_stars  INTEGER NOT NULL,
    currency      TEXT NOT NULL DEFAULT 'XTR',
    kind          TEXT NOT NULL DEFAULT 'subscription',
    period        TEXT,
    days          INTEGER,
    country_code  TEXT,
    paid_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_payload   TEXT
)
"""

PAYMENTS_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_payments_chat_id ON payments(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_payments_paid_at ON payments(paid_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_payments_kind ON payments(kind)",
]
# ─────────────────────────────────────────────────────────────
# Ініціалізація
# ─────────────────────────────────────────────────────────────


def init_schema(client: TursoClient) -> None:
    """Створює всі таблиці й індекси (idempotent).

    Можна викликати багато разів — нічого не зламається.
    Також виконує міграції для існуючих БД.
    """
    log.info("Ініціалізація схеми Turso...")

    # 1. Основні таблиці
    for sql in TABLES:
        client.execute_non_query(sql)

    # 2. Основні індекси
    for sql in INDEXES:
        client.execute_non_query(sql)

    # 3. Міграції: ALTER TABLE ADD COLUMN (idempotent)
    _apply_column_migrations(client)

    # 4. Нова таблиця payments
    client.execute_non_query(PAYMENTS_TABLE)
    for sql in PAYMENTS_INDEXES:
        client.execute_non_query(sql)

    # 5. Міграція: trial 7 днів для існуючих користувачів
    _migrate_trial_for_existing_users(client)

    log.info(
        "Схема готова: %d таблиць, %d індексів",
        len(TABLES) + 1,  # +payments
        len(INDEXES) + len(PAYMENTS_INDEXES),
    )


def _apply_column_migrations(client: TursoClient) -> None:
    """Додає нові колонки в існуючі таблиці (idempotent)."""
    for table, column, column_type in MIGRATIONS:
        try:
            rows = client.execute(f"PRAGMA table_info({table})")
            existing = {str(r[1]) for r in rows}
            if column not in existing:
                client.execute_non_query(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                log.info("Міграція: додано %s.%s (%s)", table, column, column_type)
        except Exception as e:
            log.exception("Помилка міграції %s.%s: %s", table, column, e)


def _migrate_trial_for_existing_users(client: TursoClient) -> None:
    """Дає trial 7 днів усім існуючим користувачам без trial_ends_at.

    Запускається при кожному старті — але UPDATE спрацює
    тільки для тих, у кого trial_ends_at IS NULL.

    Ідемпотентно.
    """
    from datetime import UTC, datetime, timedelta

    trial_end = (datetime.now(UTC) + timedelta(days=7)).isoformat()

    try:
        affected = client.execute_non_query(
            """
            UPDATE user_settings
            SET trial_ends_at = ?
            WHERE trial_ends_at IS NULL
            """,
            [trial_end],
        )
        if affected > 0:
            log.info("🎁 Міграція trial: %d користувачам надано 7 днів", affected)
    except Exception as e:
        log.exception("Помилка міграції trial: %s", e)
