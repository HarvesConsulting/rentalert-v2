"""NjuskaloParser — HTML-парсер Njuškalo.hr (Хорватія).

Обслуговує source 'njuskalo' (HR).
Один URL: {base_url}/{category_slug}/{city_slug}
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser

log = logging.getLogger(__name__)

BASE = "https://www.njuskalo.hr"


class NjuskaloParser(Parser):
    """Парсер Njuškalo.hr (HR)."""

    def fetch(self, city: City, categories: list[str]) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        category_slugs = self.source.config.get("category_slugs", {})
        if not category_slugs:
            log.warning("Source %r не має config.category_slugs", self.source.key)
            return []

        listings: list[Listing] = []
        seen_ids: set[str] = set()

        for cat_key in categories:
            if not self.supports_category(cat_key):
                continue

            cat_slug = category_slugs.get(cat_key)
            if not cat_slug:
                log.warning("Category %r не має slug у %r", cat_key, self.source.key)
                continue

            try:
                batch = self._fetch_category(
                    city_slug=str(city_slug),
                    category_slug=cat_slug,
                    category_key=cat_key,
                    city=city,
                )
            except Exception as e:
                log.exception("Помилка fetch %s/%s: %s", city.slug, cat_key, e)
                continue

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
    ) -> list[Listing]:
        """Завантажує одну категорію."""
        url = f"{self.source.base_url}/{category_slug}/{city_slug}"

        try:
            response = cffi_requests.get(url, impersonate="chrome", timeout=30)
        except Exception as e:
            log.warning("Njuskalo GET failed: %s", e)
            return []

        if response.status_code != 200:
            log.warning("Njuskalo %s → HTTP %d", url, response.status_code)
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Тільки звичайні оголошення (без FeaturedStore, VauVau)
        items = soup.find_all(
            "li",
            class_=lambda x: x and "EntityList-item" in x and "EntityList-item--Regular" in x,
        )

        listings: list[Listing] = []
        for li in items:
            try:
                lst = self._parse_item(
                    li=li,
                    category_key=category_key,
                    city=city,
                )
                if lst is not None:
                    listings.append(lst)
            except Exception as e:
                log.exception("Помилка парсингу li: %s", e)

        log.info("Njuskalo %s/%s: %d оголошень", city_slug, category_key, len(listings))
        return listings

    def _parse_item(
        self,
        *,
        li: Any,
        category_key: str,
        city: City,
    ) -> Listing | None:
        """Парсить один <li>."""
        # ID + link + title
        title_link = li.select_one("h3.entity-title > a")
        if title_link is None:
            return None

        ad_id = title_link.get("name", "")
        if not ad_id:
            # fallback — витягнути з href
            href = title_link.get("href", "")
            m = re.search(r"-oglas-(\d+)", href)
            ad_id = m.group(1) if m else ""
        if not ad_id:
            return None

        href = title_link.get("href", "")
        url_full = f"{BASE}{href}" if href.startswith("/") else href

        title_span = title_link.find("span")
        title = title_span.get_text(strip=True) if title_span else ""
        if not title:
            return None

        # Фото
        photo = ""
        img = li.select_one("img.entity-thumbnail-img")
        if img:
            photo = img.get("src", "") or ""
            # Покращити якість: 200x150 → 800x600
            if "image-200x150" in photo:
                photo = photo.replace("image-200x150", "image-800x600")

        # Ціна
        price = ""
        price_el = li.select_one("strong.price")
        if price_el:
            price = price_el.get_text(strip=True)

        # Description: тип + площа + локація
        description = li.select_one(".entity-description")
        location = ""
        rooms = None  # NJUSKALO не має явного поля rooms у списку

        if description:
            text = description.get_text("\n", strip=True)

            # Локація: "Lokacija:" + значення
            m = re.search(r"Lokacija:\s*\n?\s*([^\n]+)", text)
            if m:
                location = m.group(1).strip()

            # Кімнати: спроба витягнути з title (наприклад "3-sobni")
            # Кімнати: спроба витягнути з title
            # Варіанти: "3-sobni", "2S stan", "3S", "trosoban", "dvosoban"
            title_lower = title.lower()
            m_rooms = re.search(r"(\d+)-sobn", title_lower)
            if not m_rooms:
                m_rooms = re.search(r"(\d+)s\b", title_lower)
            if not m_rooms:
                # Хорватські числівники
                croatian_rooms = {
                    "jednosoban": "1",
                    "dvosoban": "2",
                    "trosoban": "3",
                    "četverosoban": "4",
                    "petosoban": "5",
                }
                for word, num in croatian_rooms.items():
                    if word in title_lower:
                        rooms = num
                        break
            if m_rooms:
                rooms = m_rooms.group(1)

        # Дата
        created_at = None
        time_el = li.select_one("time.date[datetime]")
        if time_el:
            raw = time_el.get("datetime", "")
            try:
                created_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                pass

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
            created_at=created_at,
            raw={},
        )

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Emoji + локалізована назва категорії для HR."""
        icons = {
            "apartment": "🏢",
            "house": "🏠",
            "room": "🚪",
        }
        labels = {
            "apartment": "Stanovi",
            "house": "Kuće",
            "room": "Sobe",
        }
        return icons.get(category_key, "🏠"), labels.get(category_key, category_key)
