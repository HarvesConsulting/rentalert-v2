"""OpenRentParser — парсер OpenRent.co.uk (Велика Британія).

Обслуговує source 'openrent' (GB).
Парсить HTML через BeautifulSoup.

OpenRent — платформа прямих орендодавців (без агентів).
URL пошуку: https://www.openrent.co.uk/properties-to-rent/{city_slug}
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import human_delay, stealth_headers

log = logging.getLogger(__name__)


class OpenRentParser(Parser):
    """Парсер OpenRent.co.uk (GB)."""

    def fetch(self, city: City, categories: list[str]) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        # OpenRent повертає всі категорії в одному списку — тягнемо один раз
        try:
            all_listings = self._fetch_all(city_slug=str(city_slug), city=city)
        except Exception as e:
            log.exception("OpenRent %s failed: %s", city_slug, e)
            return []

        # Фільтруємо за категоріями
        wanted = set(self.filter_categories(categories))
        if not wanted:
            return []

        result: list[Listing] = []
        for lst in all_listings:
            if lst.category in wanted:
                result.append(lst)

        log.info("OpenRent %s: %d оголошень (відфільтровано)", city_slug, len(result))
        return result

    # ─────────────────────────────────────────────────────
    # Внутрішнє
    # ─────────────────────────────────────────────────────

    def _fetch_all(self, *, city_slug: str, city: City) -> list[Listing]:
        """Завантажує всі оголошення (без фільтрації за категорією)."""
        url = f"{self.source.base_url}/properties-to-rent/{city_slug}"

        human_delay()

        response = cffi_requests.get(
            url,
            impersonate="chrome",
            headers=stealth_headers(),
            timeout=30,
        )

        if response.status_code != 200:
            log.warning("OpenRent %s → HTTP %d", url, response.status_code)
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Кожне оголошення — <a class="pli search-property-card">
        cards = soup.select("a.pli.search-property-card")
        log.info("OpenRent %s: знайдено %d карток", city_slug, len(cards))

        listings: list[Listing] = []
        for card in cards:
            try:
                lst = self._parse_card(card=card, city_slug=city.slug)
                if lst is not None:
                    listings.append(lst)
            except Exception as e:
                log.exception("Помилка парсингу картки: %s", e)

        return listings

    def _parse_card(self, *, card: Any, city_slug: str) -> Listing | None:
        """Парсить одну картку оголошення."""
        # 1. URL оголошення
        href = card.get("href", "")
        if not href:
            return None
        url_full = f"{self.source.base_url}{href}" if href.startswith("/") else href

        # 2. ID оголошення — з URL: /2865841
        m = re.search(r"/(\d+)$", href)
        if not m:
            return None
        ad_id = m.group(1)

        # 3. Заголовок — з alt фото
        img = card.find("img", class_="propertyPic")
        if img is None:
            return None
        title = (img.get("alt") or "").strip()
        if not title:
            return None

        # 4. Фото
        photo = img.get("src", "") or ""
        if photo.startswith("//"):
            photo = f"https:{photo}"

        # 5. Ціна
        price = self._extract_price(card)

        # 6. Локація — з title (після коми)
        # "1 Bed Flat, London, WC2N" → "London, WC2N"
        location = ""
        parts = title.split(",")
        if len(parts) >= 2:
            location = ", ".join(p.strip() for p in parts[1:])

        # 7. Спальні — з title ("1 Bed", "2 Bed", "3 Bed")
        rooms = None
        m_rooms = re.search(r"(\d+)\s*Bed", title, re.IGNORECASE)
        if m_rooms:
            rooms = m_rooms.group(1)

        # 8. Категорія — з title
        category_key = self._detect_category(title)
        if category_key is None:
            return None  # не наше

        icon, label = self._category_meta(category_key)

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
            created_at=None,  # OpenRent не показує час у списку
            raw={},
        )

    # ─────────────────────────────────────────────────────
    # Витягування полів
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_price(card: Any) -> str:
        """Витягує ціну з картки."""
        # OpenRent показує ціну в div з класом "pim"
        for div in card.find_all("div", class_=lambda x: x and "pim" in str(x)):
            text = div.get_text(strip=True)
            if "£" in text:
                # Додаємо пробіл між ціною і "per month"
                text = re.sub(r"(\d)(per)", r"\1 \2", text)
                return text
        # Fallback — шукаємо будь-який текст з £
        for el in card.find_all(string=re.compile(r"£\d")):
            text = el.strip()
            text = re.sub(r"(\d)(per)", r"\1 \2", text)
            return text
        return ""

    @staticmethod
    def _detect_category(title: str) -> str | None:
        """Визначає категорію за заголовком."""
        t = title.lower()
        if "room" in t or "studio" in t:
            return "room"
        if "flat" in t or "apartment" in t or "maisonette" in t:
            return "apartment"
        if "house" in t or "cottage" in t or "bungalow" in t:
            return "house"
        return None

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Emoji + локалізована назва категорії для UK."""
        icons = {
            "apartment": "🏢",
            "house": "🏠",
            "room": "🚪",
        }
        labels = {
            "apartment": "Flats",
            "house": "Houses",
            "room": "Rooms",
        }
        return icons.get(category_key, "🏠"), labels.get(category_key, category_key)
