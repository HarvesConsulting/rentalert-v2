"""HabitacliaParser — HTML-парсер Habitaclia.com (Іспанія).

Обслуговує source 'habitaclia' (ES).
Один URL повертає всі типи житла — фільтруємо за заголовком.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import (
    human_delay,
    stealth_headers,
)

log = logging.getLogger(__name__)


# Ключові слова для фільтрації категорій за заголовком
_APARTMENT_WORDS = ("piso", "apartamento", "ático", "estudio", "dúplex")
_HOUSE_WORDS = ("casa", "chalet", "villa", "adosado", "pareado")
_ROOM_WORDS = ("habitación", "cuarto")


class HabitacliaParser(Parser):
    """Парсер Habitaclia.com (ES)."""

    MAX_PAGES = 15  # запобіжник від зациклення

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення для міста й категорій (з пагінацією)."""
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        try:
            all_listings = self._fetch_all_pages(
                city_slug=str(city_slug),
                city=city,
                seen_checker=seen_checker,
            )
        except Exception as e:
            log.exception("Habitaclia %s failed: %s", city_slug, e)
            return []

        # Фільтруємо за категоріями
        wanted = set(self.filter_categories(categories))
        if not wanted:
            return []

        result: list[Listing] = []
        for lst in all_listings:
            if lst.category in wanted:
                result.append(lst)

        log.info("Habitaclia %s: %d оголошень (відфільтровано)", city_slug, len(result))
        return result

    # ─────────────────────────────────────────────────────
    # Внутрішнє
    # ─────────────────────────────────────────────────────

    def _fetch_all_pages(
        self,
        *,
        city_slug: str,
        city: City,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує всі сторінки, поки не догнали оновлення.

        Особливість: якщо на сторінці всі оголошення вже в БД — НЕ зупиняємось,
        а йдемо далі. Зупиняємось тільки якщо 3 сторінки підряд без нових.
        Це важливо для /nuevos/, де старіші оголошення можуть бути на стор. 1,
        а новіші — глибше.
        """
        all_listings: list[Listing] = []
        seen_in_run: set[str] = set()
        empty_pages_streak = 0  # скільки сторінок підряд без нових

        for page in range(1, self.MAX_PAGES + 1):
            url = self._make_page_url(city_slug, page)

            human_delay()

            try:
                response = cffi_requests.get(
                    url,
                    impersonate="chrome",
                    headers=stealth_headers(),
                    timeout=30,
                )
            except Exception as e:
                log.warning("Habitaclia GET failed (page %d): %s", page, e)
                break

            if response.status_code != 200:
                log.warning(
                    "Habitaclia %s page %d → HTTP %d",
                    city_slug,
                    page,
                    response.status_code,
                )
                break

            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.find_all("article")

            if not articles:
                log.info("Habitaclia %s: сторінка %d порожня — СТОП", city_slug, page)
                break

            page_listings: list[Listing] = []
            for art in articles:
                try:
                    lst = self._parse_article(art=art, city_slug=city.slug)
                    if lst is not None and lst.id not in seen_in_run:
                        seen_in_run.add(lst.id)
                        page_listings.append(lst)
                except Exception as e:
                    log.exception("Помилка парсингу article: %s", e)

            # Якщо сторінка взагалі порожня (усі article відкинуті) —
            # це дивно, але продовжуємо, раптом далі щось є
            if not page_listings:
                empty_pages_streak += 1
                log.info(
                    "Habitaclia %s: сторінка %d — всі дублікати (%d підряд)",
                    city_slug,
                    page,
                    empty_pages_streak,
                )
                if empty_pages_streak >= 3:
                    log.info(
                        "Habitaclia %s: 3 порожні сторінки підряд — СТОП",
                        city_slug,
                    )
                    break
                continue

            # Перевірка: чи ВСІ id зі сторінки вже в БД?
            if seen_checker:
                page_ids = [lst.id for lst in page_listings]
                if seen_checker(page_ids):
                    empty_pages_streak += 1
                    log.info(
                        "Habitaclia %s: сторінка %d — всі вже в БД (%d підряд)",
                        city_slug,
                        page,
                        empty_pages_streak,
                    )
                    if empty_pages_streak >= 3:
                        log.info(
                            "Habitaclia %s: 3 сторінки без нових — СТОП",
                            city_slug,
                        )
                        break
                    # КЛЮЧОВА ЗМІНА: не break, а continue
                    continue

            # Знайшли нові — скидаємо лічильник
            empty_pages_streak = 0

            all_listings.extend(page_listings)
            log.info(
                "Habitaclia %s: сторінка %d — %d оголошень",
                city_slug,
                page,
                len(page_listings),
            )

        return all_listings

    @staticmethod
    def _make_page_url(city_slug: str, page: int) -> str:
        """Формує URL сторінки з фільтром 'тільки нові'.

        URL: /alquiler/viviendas/{slug}/nuevos/s/{page}
        Наприклад:
          - стор. 1: /alquiler/viviendas/barcelona/nuevos/s
          - стор. 2: /alquiler/viviendas/barcelona/nuevos/s/2
          - стор. 3: /alquiler/viviendas/barcelona/nuevos/s/3
        Сортування за датою вмикається автоматично (Más recientes).
        """
        base = "https://www.habitaclia.com"
        url = f"{base}/alquiler/viviendas/{city_slug}/nuevos/s"
        if page > 1:
            url += f"/{page}"
        return url

    def _parse_article(
        self,
        *,
        art: Any,
        city_slug: str,
    ) -> Listing | None:
        """Парсить один <article>."""
        link_tag = art.find("a", attrs={"data-panot-component": "link-box-link"})
        if not link_tag:
            return None

        href = link_tag.get("href", "")
        if not href:
            return None

        # ID: підтримуємо обидва формати:
        #   1) legacy:  /i16708000002842.htm
        #   2) новий:   /alquiler/.../<UUID>/d
        m_legacy = re.search(r"/i(\d+)\.htm", href)
        m_new = re.search(
            r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/d",
            href,
        )

        if m_legacy:
            ad_id = m_legacy.group(1)
        elif m_new:
            ad_id = m_new.group(1)
        else:
            return None

        url_full = f"{self.source.base_url}{href}" if href.startswith("/") else href

        title = link_tag.get_text(strip=True)
        if not title:
            return None

        # Визначаємо категорію за заголовком
        category_key, icon, label = self._detect_category(title)
        if category_key is None:
            return None  # не наше

        price = self._extract_price(art)
        location = self._extract_location(art)
        photo = self._extract_photo(art)
        rooms, _baths, _floor = self._extract_features(art)

        if price:
            title = f"{title} — {price}"

        return Listing(
            id=self.make_id(ad_id),
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price or "—",
            location=location,
            link=url_full,
            photo=photo,
            rooms=rooms,
            area_m2=None,
            category=category_key,
            category_icon=icon,
            category_label=label,
            created_at=None,
            raw={},
        )

    # ─────────────────────────────────────────────────────
    # Витягування полів
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_price(art: Any) -> str:
        span = art.find("span", class_=lambda x: x and "text-display-4" in x)
        return span.get_text(strip=True) if span else ""

    @staticmethod
    def _extract_location(art: Any) -> str:
        span = art.find(
            "span",
            class_=lambda x: x and "truncate" in x and "whitespace-nowrap" in x,
        )
        return span.get_text(strip=True) if span else ""

    @staticmethod
    def _extract_photo(art: Any) -> str:
        img = art.find("img")
        if not img:
            return ""
        photo = img.get("src", "") or ""
        if "static.fotocasa.es" in photo:
            base = photo.split("?")[0]
            return f"{base}?rule=web_580x387_ar"
        return photo

    @staticmethod
    def _extract_features(art: Any) -> tuple[str | None, str | None, str | None]:
        """Кімнати, ванні, поверх."""
        rooms: str | None = None
        baths: str | None = None
        floor: str | None = None

        for span in art.find_all("span"):
            svg = span.find("svg")
            if not svg:
                continue
            svg_title = svg.get("data-title", "")
            text = span.get_text(strip=True)

            if svg_title == "double_bed_outline":
                m = re.search(r"(\d+)\s*hab", text)
                if m:
                    rooms = m.group(1)
            elif svg_title == "shower_outline":
                m = re.search(r"(\d+)\s*bañ", text)
                if m:
                    baths = m.group(1)
            elif svg_title == "floor_outline":
                if text and text != "—":
                    floor = text

        return rooms, baths, floor

    @staticmethod
    def _detect_category(title: str) -> tuple[str | None, str, str]:
        """Визначає категорію за заголовком."""
        t = title.lower()

        if any(w in t for w in _APARTMENT_WORDS):
            return "apartment", "🏢", "Piso"
        if any(w in t for w in _HOUSE_WORDS):
            return "house", "🏠", "Casa"
        if any(w in t for w in _ROOM_WORDS):
            return "room", "🚪", "Habitación"

        return None, "🏠", "Alquiler"
