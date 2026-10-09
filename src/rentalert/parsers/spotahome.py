"""SpotahomeParser — парсер Spotahome.com через JSON-API.

Обслуговує source 'spotahome'.

Використовує ендпоінт /api/fe/marketplace/homecards, який віддає
~200 оголошень одним запитом. Сервер ІГНОРУЄ query-параметри
(marketplace, city, page, offset) — тому фільтруємо в коді за полем
"city" кожного оголошення.

Пагінація відсутня: API завжди повертає ту саму порцію.
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from typing import Any, ClassVar

import httpx

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import human_delay

log = logging.getLogger(__name__)


# Тип Spotahome → (category_key, icon, label)
_TYPE_TO_CATEGORY: dict[str, tuple[str, str, str]] = {
    "apartment": ("apartment", "🏢", "Piso"),
    "studio": ("apartment", "🏢", "Piso"),
    "flat": ("apartment", "🏢", "Piso"),
    "house": ("house", "🏠", "Casa"),
    "chalet": ("house", "🏠", "Casa"),
    "villa": ("house", "🏠", "Casa"),
    "room_shared": ("room", "🚪", "Habitación"),
    "room_private": ("room", "🚪", "Habitación"),
    "room": ("room", "🚪", "Habitación"),
    "residence": ("apartment", "🏢", "Piso"),
}


class SpotahomeParser(Parser):
    """Парсер Spotahome.com через JSON-API (без браузера)."""

    BASE_URL = "https://www.spotahome.com"
    SEARCH_ENDPOINT: ClassVar[str] = f"{BASE_URL}/api/fe/marketplace/homecards"

    TIMEOUT_SEC = 30.0

    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": f"{BASE_URL}/",
        "Origin": BASE_URL,
    }

    # ─────────────────────────────────────────────────────────
    # Публічний API
    # ─────────────────────────────────────────────────────────

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення для міста.

        seen_checker не використовується (JSON-API не дає пагінації,
        тому рання зупинка неможлива). Параметр залишено для сумісності
        з базовим інтерфейсом Parser.
        """
        city_slug = city.slug  # канонічний slug для БД

        wanted_categories = set(self.filter_categories(categories))
        if not wanted_categories:
            return []

        human_delay(min_sec=0.5, max_sec=1.5)

        try:
            with httpx.Client(
                headers=self.HEADERS,
                timeout=self.TIMEOUT_SEC,
                follow_redirects=True,
            ) as client:
                resp = client.get(self.SEARCH_ENDPOINT)
        except httpx.HTTPError as e:
            log.warning("Spotahome %s: HTTP помилка: %s", city_slug, e)
            return []

        if resp.status_code != 200:
            log.warning(
                "Spotahome %s: %s → HTTP %d (body[:200]=%r)",
                city_slug,
                self.SEARCH_ENDPOINT,
                resp.status_code,
                resp.text[:200],
            )
            return []

        try:
            payload = resp.json()
        except ValueError:
            log.warning(
                "Spotahome %s: відповідь не JSON (content-type=%r)",
                city_slug,
                resp.headers.get("content-type"),
            )
            return []

        homecards = (payload.get("data") or {}).get("homecards") or []
        if not homecards:
            log.warning(
                "Spotahome %s: немає homecards у відповіді. keys=%s",
                city_slug,
                list(payload.keys()),
            )
            return []

        log.info(
            "Spotahome %s: отримано %d карток з API",
            city_slug,
            len(homecards),
        )

        # Список «синонімів» міста — бо Spotahome пише по-різному
        # (Malaga / Málaga, Lisbon / Lisboa, Milan / Milano, ...)
        wanted_names = self._city_aliases(city_slug)

        result: list[Listing] = []
        seen_in_run: set[str] = set()

        for raw in homecards:
            if not isinstance(raw, dict):
                continue

            # Фільтр за містом
            raw_city = str(raw.get("city") or "").strip().lower()
            if raw_city and raw_city not in wanted_names:
                continue

            try:
                lst = self._parse_one(raw, city_slug)
            except Exception as e:
                log.exception("Помилка парсингу homecard: %s", e)
                continue

            if lst is None or lst.id in seen_in_run:
                continue
            seen_in_run.add(lst.id)

            if lst.category in wanted_categories:
                result.append(lst)

        log.info(
            "Spotahome %s: %d оголошень (відфільтровано з %d)",
            city_slug,
            len(result),
            len(homecards),
        )
        return result

    # ─────────────────────────────────────────────────────────
    # Допоміжне
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _city_aliases(city_slug: str) -> set[str]:
        """Повертає всі можливі написання міста (lowercase, без діакритики)."""
        slug = city_slug.lower()
        aliases = {slug}
        extra = {
            "malaga": {"málaga"},
            "lisbon": {"lisboa"},
            "milan": {"milano"},
            "munich": {"münchen", "munchen"},
            "valencia": {"valència"},
            "warsaw": {"warszawa"},
            "prague": {"praha"},
            "vienna": {"wien"},
            "rome": {"roma"},
            "florence": {"firenze"},
            "seville": {"sevilla"},
            "turin": {"torino"},
            "naples": {"napoli"},
        }
        if slug in extra:
            aliases |= extra[slug]

        result: set[str] = set()
        for a in aliases:
            result.add(a)
            result.add(unicodedata.normalize("NFKD", a).encode("ascii", "ignore").decode("ascii"))
        return result

    def _parse_one(self, raw: dict[str, Any], city_slug: str) -> Listing | None:
        external_id = str(raw.get("id", "")).strip()
        if not external_id:
            return None

        stype = (raw.get("type") or "").lower()
        category_key, icon, label = _TYPE_TO_CATEGORY.get(stype, ("apartment", "🏢", "Piso"))

        # Ціна: pricePerMonth (число) + currencySymbol (символ)
        price_raw = raw.get("pricePerMonth")
        symbol = raw.get("currencySymbol") or "€"
        if price_raw is None:
            price = "—"
        else:
            try:
                price = f"{int(float(price_raw))} {symbol}"
            except (TypeError, ValueError):
                price = "—"

        # Локація
        loc = raw.get("location") or {}
        location_parts = [loc.get("city") or "", loc.get("street") or ""]
        location = ", ".join(p for p in location_parts if p)

        # URL
        url_path = raw.get("url") or ""
        url_full = f"{self.BASE_URL}{url_path}" if url_path.startswith("/") else url_path

        # Фото
        photo = raw.get("mainPhotoUrl") or ""

        # Кімнати / площа
        rooms_raw = raw.get("numberOfBedrooms")
        rooms = str(rooms_raw) if rooms_raw is not None else None

        area_raw = raw.get("area")
        try:
            area_m2 = float(area_raw) if area_raw else None
        except (TypeError, ValueError):
            area_m2 = None

        # Title
        title = raw.get("title") or ""
        if price and price != "—":
            title = f"{title} — {price}"

        return Listing(
            id=self.make_id(external_id),
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price,
            location=location,
            link=url_full,
            photo=photo,
            rooms=rooms,
            category=category_key,
            category_icon=icon,
            category_label=label,
            created_at=None,  # Spotahome не дає дати публікації в API
            area_m2=area_m2,
            raw=raw,
        )
