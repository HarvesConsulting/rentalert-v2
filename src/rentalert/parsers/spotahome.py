"""SpotahomeParser — парсер Spotahome.com (React Router + Playwright).

Обслуговує source 'spotahome'.

Особливість: сайт рендериться через React Router 8 — дані оголошень
не в HTML, а в window.__reactRouterDataRouter.state.loaderData.
Тому BeautifulSoup не працює — використовуємо Playwright (sync API).

Категорії:
    apartment (apartment, studio, flat)
    house (house, chalet, villa)
    room (room_shared, room_private)

Приклад:
    parser = SpotahomeParser(source)
    listings = parser.fetch(city, ["apartment", "room"])
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import human_delay

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Маппінг типів Spotahome → категорії
# ─────────────────────────────────────────────────────────────

_TYPE_TO_CATEGORY: dict[str, tuple[str, str, str]] = {
    # apartment
    "apartment": ("apartment", "🏢", "Piso"),
    "studio": ("apartment", "🏢", "Piso"),
    "flat": ("apartment", "🏢", "Piso"),
    # house
    "house": ("house", "🏠", "Casa"),
    "chalet": ("house", "🏠", "Casa"),
    "villa": ("house", "🏠", "Casa"),
    # room
    "room_shared": ("room", "🚪", "Habitación"),
    "room_private": ("room", "🚪", "Habitación"),
    "room": ("room", "🚪", "Habitación"),
}

_CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
    "PLN": "zł",
    "RON": "lei",
    "UAH": "грн",
    "MDL": "MDL",
    "CZK": "Kč",
    "BGN": "лв",
}


class SpotahomeParser(Parser):
    """Парсер Spotahome.com (Playwright + React Router loaderData)."""

    BASE_URL = "https://www.spotahome.com"
    MAX_PAGES = 10  # запобіжник від зациклення
    PAGE_WAIT_MS = 6000  # чекаємо 6 сек на рендеринг React

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
        """Завантажує оголошення для міста й категорій."""
        from playwright.sync_api import sync_playwright

        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        wanted = set(self.filter_categories(categories))
        if not wanted:
            return []

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    locale="es-ES",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                )
                page = context.new_page()

                try:
                    all_listings = self._fetch_all_pages(
                        page=page,
                        city_slug=str(city_slug),
                        city=city,
                        seen_checker=seen_checker,
                    )
                finally:
                    browser.close()
        except Exception as e:
            log.exception("Spotahome %s failed: %s", city_slug, e)
            return []

        result = [lst for lst in all_listings if lst.category in wanted]
        log.info(
            "Spotahome %s: %d оголошень (відфільтровано з %d)",
            city_slug,
            len(result),
            len(all_listings),
        )
        return result

    # ─────────────────────────────────────────────────────────
    # Пагінація
    # ─────────────────────────────────────────────────────────

    def _fetch_all_pages(
        self,
        *,
        page,
        city_slug: str,
        city: City,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує всі сторінки, поки не догнали оновлення.

        Логіка як у Habitaclia: 3 сторінки підряд без нових → стоп.
        """
        all_listings: list[Listing] = []
        seen_in_run: set[str] = set()
        empty_pages_streak = 0

        for page_num in range(1, self.MAX_PAGES + 1):
            url = self._make_page_url(city_slug, page_num)
            log.debug("Spotahome %s → стор. %d: %s", city_slug, page_num, url)

            human_delay(min_sec=1.5, max_sec=3.5)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                # Чекаємо рендеринг React Router
                page.wait_for_timeout(self.PAGE_WAIT_MS)
                # Прокрутка для підвантаження карток
                for _ in range(3):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(800)
            except Exception as e:
                log.warning(
                    "Spotahome %s page %d → помилка: %s",
                    city_slug,
                    page_num,
                    e,
                )
                break

            raw_data = self._extract_loader_data(page)
            if raw_data is None:
                log.info(
                    "Spotahome %s: стор. %d — немає loaderData, СТОП",
                    city_slug,
                    page_num,
                )
                break

            page_listings = self._parse_homecards(raw_data, city.slug)

            # Немає нових — рахуємо порожні сторінки
            new_on_page = [lst for lst in page_listings if lst.id not in seen_in_run]
            for lst in new_on_page:
                seen_in_run.add(lst.id)

            if not new_on_page:
                empty_pages_streak += 1
                log.info(
                    "Spotahome %s: стор. %d — 0 нових (%d підряд)",
                    city_slug,
                    page_num,
                    empty_pages_streak,
                )
                if empty_pages_streak >= 3:
                    log.info(
                        "Spotahome %s: 3 порожні сторінки підряд — СТОП",
                        city_slug,
                    )
                    break
                continue

            # Перевірка seen_checker
            if seen_checker:
                page_ids = [lst.id for lst in new_on_page]
                if seen_checker(page_ids):
                    empty_pages_streak += 1
                    log.info(
                        "Spotahome %s: стор. %d — всі вже в БД (%d підряд)",
                        city_slug,
                        page_num,
                        empty_pages_streak,
                    )
                    if empty_pages_streak >= 3:
                        log.info(
                            "Spotahome %s: 3 сторінки без нових — СТОП",
                            city_slug,
                        )
                        break
                    continue

            empty_pages_streak = 0
            all_listings.extend(new_on_page)
            log.info(
                "Spotahome %s: стор. %d — %d нових",
                city_slug,
                page_num,
                len(new_on_page),
            )

        return all_listings

    @staticmethod
    def _make_page_url(city_slug: str, page_num: int) -> str:
        """Формує URL сторінки.

        URL: /s/{slug}?page=N
        """
        base = f"https://www.spotahome.com/s/{city_slug}"
        if page_num > 1:
            base += f"?page={page_num}"
        return base

    # ─────────────────────────────────────────────────────────
    # Витягування даних з React Router
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_loader_data(page) -> dict[str, Any] | None:
        """Витягує marketplace-search з React Router loaderData."""
        try:
            data = page.evaluate("""
                () => {
                    const r = window.__reactRouterDataRouter;
                    if (!r?.state?.loaderData) return null;
                    const ms = r.state.loaderData['marketplace-search'];
                    if (!ms) return null;
                    return {
                        city: ms.city,
                        cityName: ms.carouselCityName,
                        currency: ms.currencyIsoCode || 'EUR',
                        priceUnit: ms.carouselPriceUnit || 'month',
                        homecards: ms.initialHomecards,
                    };
                }
            """)
            # page.evaluate() повертає Any — валідуємо тип
            if not isinstance(data, dict):
                return None
            return data
        except Exception as e:
            log.warning("Spotahome: помилка витягування loaderData: %s", e)
            return None

    # ─────────────────────────────────────────────────────────
    # Парсинг карток
    # ─────────────────────────────────────────────────────────

    def _parse_homecards(
        self,
        raw_data: dict[str, Any],
        city_slug: str,
    ) -> list[Listing]:
        """Парсить initialHomecards → list[Listing]."""
        homecards = raw_data.get("homecards")
        if not homecards:
            return []

        # initialHomecards може бути dict (id → listing) або list
        raw_listings = list(homecards.values()) if isinstance(homecards, dict) else list(homecards)

        currency = raw_data.get("currency", "EUR")
        result: list[Listing] = []

        for raw in raw_listings:
            try:
                lst = self._parse_one(raw, city_slug, currency)
                if lst is not None:
                    result.append(lst)
            except Exception as e:
                log.exception("Помилка парсингу homecard: %s", e)

        return result

    def _parse_one(
        self,
        raw: dict[str, Any],
        city_slug: str,
        currency: str,
    ) -> Listing | None:
        """Парсить одну картку."""
        external_id = str(raw.get("id", "")).strip()
        if not external_id:
            return None

        # Категорія
        stype = (raw.get("type") or "").lower()
        cat_tuple = _TYPE_TO_CATEGORY.get(stype)
        if cat_tuple is None:
            cat_tuple = ("apartment", "🏢", "Piso")
        category_key, icon, label = cat_tuple

        # Ціна
        price = self._format_price(raw.get("displayPrice"), currency)

        # Локація
        loc = raw.get("location") or {}
        location_parts = [
            loc.get("city") or "",
            loc.get("street") or "",
        ]
        location = ", ".join(p for p in location_parts if p)

        # URL
        url_path = raw.get("url") or ""
        url_full = f"{self.BASE_URL}{url_path}" if url_path.startswith("/") else url_path

        # Фото
        photo = raw.get("mainPhotoUrl") or ""

        # Кімнати
        rooms_raw = raw.get("numberOfBedrooms")
        rooms = str(rooms_raw) if rooms_raw is not None else None

        # Площа
        area_raw = raw.get("area")
        try:
            area_m2 = float(area_raw) if area_raw is not None else None
        except (TypeError, ValueError):
            area_m2 = None

        # Title — додаємо ціну, як у Habitaclia
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
            created_at=None,  # Spotahome не дає точної дати
            area_m2=area_m2,
            raw=raw,
        )

    @staticmethod
    def _format_price(display_price: Any, currency: str) -> str:
        """Формує рядок ціни: '940 €' або '1234.56 €'.

        Підтримує обидва формати:
          • "1234.56"  — крапка як десяткова
          • "1.234,56" — кома як десяткова, крапка як тисячі
          • "1,234.56" — кома як тисячі, крапка як десяткова
        """
        if display_price is None or display_price == "":
            return "—"
        try:
            s = str(display_price).strip()
            s = re.sub(r"[^\d.,]", "", s)

            if not s:
                return "—"

            # Визначаємо десятковий розділювач
            dot_pos = s.rfind(".")
            comma_pos = s.rfind(",")

            if dot_pos == -1 and comma_pos == -1:
                # Немає розділювачів: "940"
                val = float(s)
            elif dot_pos > comma_pos:
                # Крапка правіше: "1234.56" або "1,234.56" — крапка десяткова
                s = s.replace(",", "")  # видаляємо коми-тисячні
                val = float(s)
            elif comma_pos > dot_pos:
                # Кома правіше: "1.234,56" — кома десяткова
                s = s.replace(".", "")  # видаляємо крапки-тисячні
                s = s.replace(",", ".")
                val = float(s)
            else:
                # Рівні позиції (не мало б бути) — fallback
                val = float(s.replace(",", "."))

            symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency)
            if val.is_integer():
                return f"{int(val)} {symbol}"
            return f"{val:.2f} {symbol}"
        except (ValueError, TypeError):
            return "—"
