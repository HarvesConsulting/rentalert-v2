"""HabitacliaParser — HTML-парсер Habitaclia.com (Іспанія).

Обслуговує source 'habitaclia' (ES).
Один URL повертає всі типи житла — фільтруємо за заголовком.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser

log = logging.getLogger(__name__)


# Ключові слова для фільтрації категорій за заголовком
_APARTMENT_WORDS = ("piso", "apartamento", "ático", "estudio", "dúplex")
_HOUSE_WORDS = ("casa", "chalet", "villa", "adosado", "pareado")
_ROOM_WORDS = ("habitación", "cuarto")


class HabitacliaParser(Parser):
    """Парсер Habitaclia.com (ES)."""

    def fetch(self, city: City, categories: list[str]) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        # Один URL повертає все — тягнемо один раз
        try:
            all_listings = self._fetch_all(city_slug=str(city_slug), city=city)
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

    def _fetch_all(self, *, city_slug: str, city: City) -> list[Listing]:
        """Завантажує всі оголошення (без фільтрації за категорією)."""
        url = f"{self.source.base_url}/alquiler-{city_slug}.htm"

        try:
            response = cffi_requests.get(url, impersonate="chrome", timeout=30)
        except Exception as e:
            log.warning("Habitaclia GET failed: %s", e)
            return []

        if response.status_code != 200:
            log.warning("Habitaclia %s → HTTP %d", url, response.status_code)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article")

        listings: list[Listing] = []
        for art in articles:
            try:
                lst = self._parse_article(art=art, city_slug=city.slug)
                if lst is not None:
                    listings.append(lst)
            except Exception as e:
                log.exception("Помилка парсингу article: %s", e)

        log.info("Habitaclia %s: %d сирих оголошень", city_slug, len(listings))
        return listings

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

        # ID з URL: /i16708000002842.htm → 16708000002842
        m = re.search(r"/i(\d+)\.htm", href)
        if not m:
            return None
        ad_id = m.group(1)

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
            category=category_key,
            category_icon=icon,
            category_label=label,
            created_at=None,  # Habitaclia не показує час у списку
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
