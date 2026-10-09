"""Розрахунок ринкових цін і Deal Score.

Ідея:
  - Раз на добу беремо всі оголошення з площею (`area_m2`)
    і ціною за останні N днів.
  - Групуємо по (city_slug, location_key), де location_key =
    "sector|category|rooms".
  - Рахуємо медіану ціни за м².
  - Записуємо в market_prices.

  При показі оголошення:
  - Порівнюємо price_m2 оголошення з медіаною його групи.
  - Повертаємо DealScore з емодзі, текстом і ratio.
"""

from __future__ import annotations

import logging
import re
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from rentalert.db.client import TursoClient

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Типи
# ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DealScore:
    """Оцінка вигідності оголошення."""

    emoji: str
    label: str
    ratio: float
    sample_size: int


# ─────────────────────────────────────────────────────────────
# Парсери
# ─────────────────────────────────────────────────────────────


_PRICE_RE = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)")


def parse_price(price_str: str | None) -> float | None:
    """'450 €' → 450.0; '1 200 MDL' → 1200.0; '—' → None."""
    if not price_str:
        return None
    cleaned = price_str.replace(" ", "").replace("\u00a0", "")
    m = _PRICE_RE.search(cleaned)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_currency(price_str: str | None) -> str:
    """'450 €' → '€'; '1 200 MDL' → 'MDL'; '—' → '?'."""
    if not price_str:
        return "?"
    if "€" in price_str:
        return "€"
    if "$" in price_str:
        return "$"
    if "MDL" in price_str:
        return "MDL"
    return "?"


# ─────────────────────────────────────────────────────────────
# Ключ групи
# ─────────────────────────────────────────────────────────────


def make_location_key(
    city_slug: str,
    location: str | None,
    category: str,
    rooms: str | None,
) -> str:
    """Формує ключ групи для порівняння цін.

    Формати location:
      Habitaclia: "Centro, Madrid Capital"              → sector = "centro"
      Pisos:      "Sol (Distrito Centro, Madrid Capital)" → sector = "sol"

    Логіка:
      1. Прибираємо все в дужках разом з дужками (там часто сміття).
      2. Беремо ПЕРШИЙ компонент до коми (район).
      3. Нормалізуємо пробіли.
    """
    loc = (location or "").lower()
    # 1. Прибираємо все в дужках разом з дужками
    loc = re.sub(r"\([^)]*\)", "", loc)
    # 2. Беремо перший компонент до коми
    sector = loc.split(",")[0].strip()
    # 3. Якщо порожньо — city_slug
    if not sector:
        sector = city_slug
    # 4. Нормалізуємо пробіли
    sector = re.sub(r"\s+", " ", sector).strip()

    rooms_key = rooms or "any"
    return f"{city_slug}|{sector}|{category}|{rooms_key}"


# ─────────────────────────────────────────────────────────────
# Перерахунок медіан
# ─────────────────────────────────────────────────────────────


def recompute_market_prices(
    client: TursoClient,
    *,
    days: int = 30,
    min_sample: int = 2,
) -> int:
    """Рахує медіани ціни за м² і пише в market_prices.

    Args:
        days: вікно свіжості (останні N днів).
        min_sample: мінімум оголошень у групі.

    Returns:
        Кількість оновлених груп.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    rows = client.execute(
        """
        SELECT city_slug, location, category, rooms, price, area_m2
        FROM seen_listings
        WHERE area_m2 IS NOT NULL AND area_m2 > 0
          AND price IS NOT NULL AND price != ''
          AND first_seen >= ?
        """,
        [cutoff],
    )

    groups: dict[tuple[str, str], list[float]] = {}
    skipped_parse = 0

    for city_slug, location, category, rooms, price_str, area in rows:
        price = parse_price(price_str)
        if price is None:
            skipped_parse += 1
            continue
        try:
            area_f = float(area)
        except (TypeError, ValueError):
            skipped_parse += 1
            continue
        if area_f <= 0:
            continue
        price_m2 = price / area_f
        # Sanity: відсіюємо явні помилки
        if price_m2 < 1.0 or price_m2 > 10000:
            continue
            # Відсіюємо residence/coliving з аномально великою кількістю кімнат
        try:
            rooms_int = int(rooms) if rooms else 0
        except (TypeError, ValueError):
            rooms_int = 0
        if rooms_int > 15:
            continue
        key = make_location_key(
            str(city_slug),
            location,
            str(category or ""),
            rooms,
        )
        groups.setdefault((str(city_slug), key), []).append(price_m2)

        # Fallback-група по місту (без району) — для випадків,
        # коли точний район невідомий, або Pisos/Habitaclia
        # використовують різні назви районів.
        city_key = f"{city_slug}|{city_slug}|{category or ''}|{rooms or 'any'}"
        groups.setdefault((str(city_slug), city_key), []).append(price_m2)

    count = 0
    for (city_slug, key), prices in groups.items():
        if len(prices) < min_sample:
            continue
        median = statistics.median(prices)
        client.execute_non_query(
            """
            INSERT INTO market_prices
                (city_slug, location_key, median_price_m2, sample_size, computed_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(city_slug, location_key) DO UPDATE SET
                median_price_m2 = excluded.median_price_m2,
                sample_size = excluded.sample_size,
                computed_at = CURRENT_TIMESTAMP
            """,
            [city_slug, key, median, len(prices)],
        )
        count += 1

    log.info(
        "market_prices: оновлено %d груп (пропущено %d рядків)",
        count,
        skipped_parse,
    )
    return count


# ─────────────────────────────────────────────────────────────
# Deal Score
# ─────────────────────────────────────────────────────────────


def get_deal_score(
    client: TursoClient,
    *,
    city_slug: str,
    location: str | None,
    category: str,
    rooms: str | None,
    price_str: str,
    area_m2: float | None,
) -> DealScore | None:
    """Повертає Deal Score або None, якщо даних недостатньо."""
    if area_m2 is None or area_m2 <= 0:
        return None
    price = parse_price(price_str)
    if price is None or price <= 0:
        return None
    price_m2 = price / area_m2

    key = make_location_key(city_slug, location, category, rooms)
    rows = client.execute(
        """
        SELECT median_price_m2, sample_size
        FROM market_prices
        WHERE city_slug = ? AND location_key = ?
        """,
        [city_slug, key],
    )

    # Fallback: якщо точної групи немає — пробуємо групу по місту.
    if not rows:
        city_key = f"{city_slug}|{city_slug}|{category}|{rooms or 'any'}"
        rows = client.execute(
            """
            SELECT median_price_m2, sample_size
            FROM market_prices
            WHERE city_slug = ? AND location_key = ?
            """,
            [city_slug, city_key],
        )

    if not rows:
        return None
    median, sample_size = rows[0]
    try:
        median_f = float(median)
    except (TypeError, ValueError):
        return None
    if median_f <= 0:
        return None

    ratio = price_m2 / median_f
    n = int(sample_size or 0)

    if ratio < 0.7:
        return DealScore(
            "🔥",
            f"Дуже вигідно (−{round((1 - ratio) * 100)}%)",
            ratio,
            n,
        )
    if ratio < 0.9:
        return DealScore(
            "✅",
            f"Вигідно (−{round((1 - ratio) * 100)}%)",
            ratio,
            n,
        )
    if ratio < 1.1:
        return DealScore("➖", "У ринковій ціні", ratio, n)
    if ratio < 1.3:
        return DealScore(
            "⚠️",
            f"Дорожче за ринок (+{round((ratio - 1) * 100)}%)",
            ratio,
            n,
        )
    return DealScore(
        "🚨",
        f"Переоцінено (+{round((ratio - 1) * 100)}%)",
        ratio,
        n,
    )
