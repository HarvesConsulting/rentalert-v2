"""SpotahomeParser — парсер Spotahome.com через JSON-API.

Обслуговує source 'spotahome'.

Раніше використовував Playwright + React Router loaderData, але це
на Render Free (512 MB) стабільно падало без логів — Chromium з'їдав
пам'ять і процес убивався ззовні.

Тепер: намагаємось витягнути дані з JSON-ендпоінта, який використовує
сам фронтенд. Якщо ендпоінт не відповідає або структура змінилась —
повертаємо [] і пишемо детальний warning у логи.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any, ClassVar

import httpx

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import human_delay

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Маппінг типів Spotahome → категорії
# ─────────────────────────────────────────────────────────────

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
}

_CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€", "USD": "$", "GBP": "£", "PLN": "zł",
    "RON": "lei", "UAH": "грн", "MDL": "MDL", "CZK": "Kč", "BGN": "лв",
}


class SpotahomeParser(Parser):
    """Парсер Spotahome.com через JSON-API (без браузера)."""

    BASE_URL = "https://www.spotahome.com"
    MAX_PAGES = 10
    PAGE_SIZE = 30  # скільки карток на сторінку просити
    TIMEOUT_SEC = 25.0
    MAX_EMPTY_PAGES = 3  # 3 порожні сторінки підряд → стоп

    # Ендпоінт, який використовує фронтенд для пошуку.
    # ⚠️ Якщо він не працює — побачиш warning у логах, і ми підберемо інший.
    SEARCH_ENDPOINT: ClassVar[str] = (
        "https://www.spotahome.com/api/public/marketplace-search"
    )

    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.spotahome.com/",
        "Origin": "https://www.spotahome.com",
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
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        wanted = set(self.filter_categories(categories))
        if not wanted:
            return []

        try:
            all_listings = self._fetch_all_pages(
                city_slug=str(city_slug),
                city=city,
                seen_checker=seen_checker,
            )
        except Exception as e:
            log.exception("Spotahome %s failed: %s", city_slug, e)
            return []

        result = [lst for lst in all_listings if lst.category in wanted]
        log.info(
            "Spotahome %s: %d оголошень (відфільтровано з %d)",
            city_slug, len(result), len(all_listings),
        )
        return result

    # ─────────────────────────────────────────────────────────
    # Пагінація
    # ─────────────────────────────────────────────────────────

    def _fetch_all_pages(
        self,
        *,
        city_slug: str,
        city: City,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        all_listings: list[Listing] = []
        seen_in_run: set[str] = set()
        empty_streak = 0

        with httpx.Client(
            headers=self.HEADERS,
            timeout=self.TIMEOUT_SEC,
            follow_redirects=True,
            http2=False,  # http2 іноді ламає Cloudflare-фронти
        ) as client:
            for page_num in range(1, self.MAX_PAGES + 1):
                human_delay(min_sec=0.8, max_sec=2.0)

                payload = self._request_page(client, city_slug, page_num)
                if payload is None:
                    log.info(
                        "Spotahome %s: стор. %d — немає даних, СТОП",
                        city_slug, page_num,
                    )
                    break

                page_listings = self._parse_homecards(payload, city.slug)

                new_on_page = [lst for lst in page_listings if lst.id not in seen_in_run]
                for lst in new_on_page:
                    seen_in_run.add(lst.id)

                if not new_on_page:
                    empty_streak += 1
                    log.info(
                        "Spotahome %s: стор. %d — 0 нових (%d підряд)",
                        city_slug, page_num, empty_streak,
                    )
                    if empty_streak >= self.MAX_EMPTY_PAGES:
                        log.info(
                            "Spotahome %s: %d порожніх сторінок підряд — СТОП",
                            city_slug, self.MAX_EMPTY_PAGES,
                        )
                        break
                    continue

                if seen_checker:
                    page_ids = [lst.id for lst in new_on_page]
                    if seen_checker(page_ids):
                        empty_streak += 1
                        log.info(
                            "Spotahome %s: стор. %d — всі вже в БД (%d підряд)",
                            city_slug, page_num, empty_streak,
                        )
                        if empty_streak >= self.MAX_EMPTY_PAGES:
                            log.info(
                                "Spotahome %s: %d сторінок без нових — СТОП",
                                city_slug, self.MAX_EMPTY_PAGES,
                            )
                            break
                        continue

                empty_streak = 0
                all_listings.extend(new_on_page)
                log.info(
                    "Spotahome %s: стор. %d — %d нових",
                    city_slug, page_num, len(new_on_page),
                )

        return all_listings

    # ─────────────────────────────────────────────────────────
    # HTTP-запит
    # ─────────────────────────────────────────────────────────

    def _request_page(
        self, client: httpx.Client, city_slug: str, page_num: int,
    ) -> dict[str, Any] | None:
        """Робить один запит до JSON-API. Повертає dict або None."""

        params = {
            "city": city_slug,
            "page": page_num,
            "pageSize": self.PAGE_SIZE,
        }

        try:
            resp = client.get(self.SEARCH_ENDPOINT, params=params)
        except httpx.HTTPError as e:
            log.warning("Spotahome %s: HTTP помилка: %s", city_slug, e)
            return None

        if resp.status_code != 200:
            log.warning(
                "Spotahome %s: %s → HTTP %d (body[:200]=%r)",
                city_slug, self.SEARCH_ENDPOINT,
                resp.status_code, resp.text[:200],
            )
            return None

        try:
            data = resp.json()
        except ValueError:
            log.warning(
                "Spotahome %s: відповідь не JSON (content-type=%r, body[:200]=%r)",
                city_slug, resp.headers.get("content-type"), resp.text[:200],
            )
            return None

        if not isinstance(data, dict):
            log.warning(
                "Spotahome %s: JSON не dict, а %s", city_slug, type(data).__name__,
            )
            return None

        # Діагностика: що взагалі в ключах відповіді.
        # Це допоможе підібрати правильний шлях, якщо структура інша.
        log.info(
            "Spotahome %s: стор. %d — ключі JSON: %s",
            city_slug, page_num, list(data.keys()),
        )

        return data

    # ─────────────────────────────────────────────────────────
    # Парсинг
    # ─────────────────────────────────────────────────────────

    def _parse_homecards(
        self, payload: dict[str, Any], city_slug: str,
    ) -> list[Listing]:
        """Витягує список карток з відповіді.

        Пробує кілька можливих шляхів, бо структура може відрізнятись
        залежно від версії API.
        """
        homecards = (
            payload.get("homecards")
            or payload.get("initialHomecards")
            or (payload.get("data") or {}).get("homecards")
            or (payload.get("data") or {}).get("initialHomecards")
        )
        if not homecards:
            log.warning(
                "Spotahome %s: не знайдено homecards у відповіді. keys=%s",
                city_slug, list(payload.keys()),
            )
            return []

        if isinstance(homecards, dict):
            raw_listings = list(homecards.values())
        elif isinstance(homecards, list):
            raw_listings = homecards
        else:
            log.warning(
                "Spotahome %s: homecards несподіваного типу: %s",
                city_slug, type(homecards).__name__,
            )
            return []

        currency = (
            payload.get("currency")
            or payload.get("currencyIsoCode")
            or (payload.get("data") or {}).get("currencyIsoCode")
            or "EUR"
        )

        result: list[Listing] = []
        for raw in raw_listings:
            if not isinstance(raw, dict):
                continue
            try:
                lst = self._parse_one(raw, city_slug, currency)
                if lst is not None:
                    result.append(lst)
            except Exception as e:
                log.exception("Помилка парсингу homecard: %s", e)

        return result

    def _parse_one(
        self, raw: dict[str, Any], city_slug: str, currency: str,
    ) -> Listing | None:
        external_id = str(raw.get("id", "")).strip()
        if not external_id:
            return None

        stype = (raw.get("type") or "").lower()
        cat_tuple = _TYPE_TO_CATEGORY.get(stype, ("apartment", "🏢", "Piso"))
        category_key, icon, label = cat_tuple

        price = self._format_price(raw.get("displayPrice"), currency)

        loc = raw.get("location") or {}
        location_parts = [loc.get("city") or "", loc.get("street") or ""]
        location = ", ".join(p for p in location_parts if p)

        url_path = raw.get("url") or ""
        url_full = f"{self.BASE_URL}{url_path}" if url_path.startswith("/") else url_path

        photo = raw.get("mainPhotoUrl") or ""

        rooms_raw = raw.get("numberOfBedrooms")
        rooms = str(rooms_raw) if rooms_raw is not None else None

        area_raw = raw.get("area")
        try:
            area_m2 = float(area_raw) if area_raw is not None else None
        except (TypeError, ValueError):
            area_m2 = None

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
            created_at=None,
            area_m2=area_m2,
            raw=raw,
        )

    @staticmethod
    def _format_price(display_price: Any, currency: str) -> str:
        if display_price is None or display_price == "":
            return "—"
        try:
            s = str(display_price).strip()
            s = re.sub(r"[^\d.,]", "", s)
            if not s:
                return "—"

            dot_pos = s.rfind(".")
            comma_pos = s.rfind(",")

            if dot_pos == -1 and comma_pos == -1:
                val = float(s)
            elif dot_pos > comma_pos:
                s = s.replace(",", "")
                val = float(s)
            elif comma_pos > dot_pos:
                s = s.replace(".", "")
                s = s.replace(",", ".")
                val = float(s)
            else:
                val = float(s.replace(",", "."))

            symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency)
            if val.is_integer():
                return f"{int(val)} {symbol}"
            return f"{val:.2f} {symbol}"
        except (ValueError, TypeError):
            return "—"
