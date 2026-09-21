"""NekretnineParser — HTML-парсер Nekretnine.hr (Хорватія).

Обслуговує source 'nekretnine' (HR).

Особливості:
- Квартири: /najam-stanovi/{city}/
- Будинки: /najam-stambene-nekretnine/{city}/ + фільтр по title (Kuća, Vila)
- Фото: pic.nekretnine.hr/image/{id}/xxs-c.jpg → l-c.jpg
- ID: з URL /oglasi/{id}/
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

BASE = "https://www.nekretnine.hr"

# Ключові слова для фільтрації будинків зі stambene-nekretnine
HOUSE_KEYWORDS = ("kuća", "kuca", "vila", "samostalna", "dvojna", "obiteljska")


class NekretnineParser(Parser):
    """Парсер Nekretnine.hr (HR)."""

    def fetch(self, city: City, categories: list[str]) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        listings: list[Listing] = []
        seen_ids: set[str] = set()

        # 1. Квартири
        if "apartment" in categories:
            batch = self._fetch_category(
                city_slug=str(city_slug),
                category_slug="najam-stanovi",
                category_key="apartment",
                city=city,
                filter_house=False,
            )
            for lst in batch:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    listings.append(lst)

        # 2. Будинки (з фільтром зі stambene-nekretnine)
        if "house" in categories:
            batch = self._fetch_category(
                city_slug=str(city_slug),
                category_slug="najam-stambene-nekretnine",
                category_key="house",
                city=city,
                filter_house=True,
            )
            for lst in batch:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    listings.append(lst)

        return listings

    # ─────────────────────────────────────────────────────
    # Внутрішнє
    # ─────────────────────────────────────────────────────

    def _fetch_category(
        self,
        *,
        city_slug: str,
        category_slug: str,
        category_key: str,
        city: City,
        filter_house: bool,
    ) -> list[Listing]:
        """Завантажує одну категорію.

        filter_house=True — залишаємо ТІЛЬКИ будинки (Kuća, Vila).
        filter_house=False — залишаємо ТІЛЬКИ квартири (Stan).
        """
        url = f"{self.source.base_url}/{category_slug}/{city_slug}/"

        try:
            response = cffi_requests.get(url, impersonate="chrome", timeout=30)
        except Exception as e:
            log.warning("Nekretnine GET failed: %s", e)
            return []

        if response.status_code != 200:
            log.warning("Nekretnine %s → HTTP %d", url, response.status_code)
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        items = soup.find_all(
            "div",
            class_=lambda x: x and "Property_card" in (x if isinstance(x, str) else " ".join(x)),
        )

        log.info("Nekretnine %s: знайдено %d карток", url, len(items))

        listings: list[Listing] = []
        for card in items:
            try:
                lst = self._parse_card(card=card, city=city, category_key=category_key)
                if lst is None:
                    continue

                # Фільтр за типом
                title_lower = lst.title.lower()
                is_house = any(kw in title_lower for kw in HOUSE_KEYWORDS)

                if filter_house and not is_house:
                    continue  # хочемо будинки, а знайшли квартиру
                if not filter_house and is_house:
                    continue  # хочемо квартири, а знайшли будинок

                listings.append(lst)
            except Exception as e:
                log.exception("Nekretnine parse card error: %s", e)

        log.info(
            "Nekretnine %s/%s: %d оголошень (після фільтра)",
            city_slug,
            category_key,
            len(listings),
        )
        return listings

    def _parse_card(
        self,
        *,
        card: Any,
        city: City,
        category_key: str,
    ) -> Listing | None:
        """Парсить одну картку оголошення."""
        # Title + location
        title_el = card.select_one('[class*="Title_title"]')
        if title_el is None:
            return None

        title_full = title_el.get_text(strip=True)
        if not title_full:
            return None

        # Розбиваємо "Dvosobni stan Rudeš, Trešnjevka - Sjever, Zagreb" на частини
        parts = [p.strip() for p in title_full.split(",") if p.strip()]
        if not parts:
            return None

        title = parts[0]
        city_name = parts[-1] if len(parts) > 1 else ""
        regions = (
            ", ".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) == 2 else "")
        )
        location = f"{regions}, {city_name}" if regions else city_name

        # URL + ID
        link_el = card.select_one('a[href*="/oglasi/"]')
        if link_el is None:
            return None

        href = link_el.get("href", "")
        m = re.search(r"/oglasi/(\d+)/", href)
        if not m:
            return None

        ad_id = m.group(1)
        url_full = f"{BASE}{href}" if href.startswith("/") else href

        # Ціна
        price = ""
        price_el = card.select_one('[class*="Price_price"]')
        if price_el:
            price = price_el.get_text(strip=True)

        # Фото
        photo = ""
        img = card.select_one('img[src*="pic.nekretnine.hr"]')
        if img:
            photo = img.get("src", "") or ""
            # xxs-c → l-c (1280×960)
            if "xxs-c" in photo:
                photo = photo.replace("xxs-c", "l-c")

        # Кімнати: спроба з title (npr. "Dvosobni", "Trosobni", "3-sobni")
        rooms = self._extract_rooms(title)

        icon, label = self._category_meta(category_key)

        return Listing(
            id=self.make_id(ad_id),
            source_key=self.source.key,
            city_slug=city.slug,
            title=title,
            price=price or "—",
            location=location,
            link=url_full,
            photo=photo,
            rooms=rooms,
            category=category_key,
            category_icon=icon,
            category_label=label,
            created_at=None,  # Nekretnine.hr не показує час у списку
            raw={},
        )

    @staticmethod
    def _extract_rooms(title: str) -> str | None:
        """Витягує кількість кімнат з title (хорватською)."""
        t = title.lower()

        # Числові: "3-sobni", "2 sobni", "1-soban"
        m = re.search(r"(\d+)[\s-]?sobn", t)
        if m:
            return m.group(1)

        # Словесні
        word_map = {
            "jednosobni": "1",
            "jednosoban": "1",
            "dvosobni": "2",
            "dvosoban": "2",
            "trosobni": "3",
            "trosoban": "3",
            "četverosobni": "4",
            "četverosoban": "4",
            "petosobni": "5",
            "petosoban": "5",
            "garsonijera": "1",
        }
        for word, num in word_map.items():
            if word in t:
                return num

        return None

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Emoji + локалізована назва категорії для HR."""
        icons = {
            "apartment": "🏢",
            "house": "🏠",
        }
        labels = {
            "apartment": "Stanovi",
            "house": "Kuće",
        }
        return icons.get(category_key, "🏠"), labels.get(category_key, category_key)
