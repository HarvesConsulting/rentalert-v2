"""RightmoveParser — парсер Rightmove.co.uk (Велика Британія)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import human_delay, stealth_headers

log = logging.getLogger(__name__)


class RightmoveParser(Parser):
    """Парсер Rightmove (UK)."""

    def fetch(self, city: City, categories: list[str]) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        location_id = self.external_id(city)
        if location_id is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        listings: list[Listing] = []
        seen_ids: set[str] = set()

        for cat_key in categories:
            if not self.supports_category(cat_key):
                continue

            try:
                batch = self._fetch_category(
                    location_id=str(location_id),
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
        location_id: str,
        category_key: str,
        city: City,
    ) -> list[Listing]:
        """Завантажує одну категорію (сторінку пошуку)."""
        # Формуємо URL пошуку
        base_url = f"{self.source.base_url}/property-to-rent/find.html"
        params = {
            "locationIdentifier": location_id,
            "index": 0,
            "channel": "RENT",
            "propertyTypes": "",  # можна додати фільтри
        }

        human_delay()

        response = cffi_requests.get(
            base_url,
            params=params,
            impersonate="chrome",
            headers=stealth_headers(),
            timeout=30,
        )

        if response.status_code != 200:
            log.warning("Rightmove %s/%s → HTTP %d", city.slug, category_key, response.status_code)
            return []

        # 1. Витягуємо список URL оголошень зі сторінки пошуку
        property_urls = self._extract_property_urls(response.text)
        log.info(
            "Rightmove %s/%s: знайдено %d оголошень на сторінці",
            city.slug,
            category_key,
            len(property_urls),
        )

        # 2. Для кожного URL завантажуємо сторінку оголошення і витягуємо PAGE_MODEL
        listings: list[Listing] = []
        for prop_url in property_urls[:10]:  # обмежимо для тесту
            try:
                listing = self._fetch_property(prop_url, city.slug, category_key)
                if listing is not None:
                    listings.append(listing)
            except Exception as e:
                log.exception("Помилка парсингу %s: %s", prop_url, e)
            human_delay(1.0, 2.0)

        return listings

    @staticmethod
    def _extract_property_urls(html: str) -> list[str]:
        """Витягує URL оголошень зі сторінки пошуку."""
        # Rightmove використовує посилання виду /properties/12345678
        pattern = re.compile(r'href="(/properties/\d+[^"]*)"')
        matches = pattern.findall(html)
        # Дедуплікація зі збереженням порядку
        seen = set()
        result = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result

    def _fetch_property(self, path: str, city_slug: str, category_key: str) -> Listing | None:
        """Завантажує сторінку оголошення і витягує дані."""
        url = f"{self.source.base_url}{path}"

        human_delay()

        response = cffi_requests.get(
            url,
            impersonate="chrome",
            headers=stealth_headers(),
            timeout=30,
        )

        if response.status_code != 200:
            return None

        # Витягуємо PAGE_MODEL JSON
        page_model = self._extract_page_model(response.text)
        if not page_model:
            return None

        pd = page_model.get("propertyData", {})

        # ID
        item_id = str(pd.get("id", ""))
        if not item_id:
            return None

        # Ціна
        prices = pd.get("prices", {})
        price = prices.get("primaryPrice", "") or "—"

        # Адреса
        address_info = pd.get("address", {})
        location = address_info.get("displayAddress", "")

        # Кімнати
        rooms = pd.get("bedrooms")
        rooms_str = str(rooms) if rooms else None

        # Фото
        photos = pd.get("images", []) or []
        photo = photos[0].get("url", "") if photos else ""

        # Опис
        description = pd.get("text", {}).get("description", "") or ""

        icon, label = self._category_meta(category_key)

        return Listing(
            id=self.make_id(item_id),
            source_key=self.source.key,
            city_slug=city_slug,
            title=description[:100] or f"Property in {location}"[:100],
            price=price,
            location=location,
            link=url,
            photo=photo,
            rooms=rooms_str,
            category=category_key,
            category_icon=icon,
            category_label=label,
            created_at=None,
            raw={"description": description[:300]},
        )

    @staticmethod
    def _extract_page_model(html: str) -> dict[str, Any] | None:
        """Витягує window.PAGE_MODEL JSON з HTML."""
        # Знаходимо початок
        marker = "window.PAGE_MODEL = "
        start = html.find(marker)
        if start == -1:
            return None
        start += len(marker)

        # Рахуємо дужки, щоб знайти кінець JSON-об'єкта
        depth = 0
        i = start
        while i < len(html):
            if html[i] == "{":
                depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1

        if depth != 0:
            return None

        try:
            return json.loads(html[start : i + 1])
        except json.JSONDecodeError:
            return None

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Emoji + локалізована назва категорії для UK."""
        icons = {"apartment": "🏢", "house": "🏠", "room": "🚪"}
        labels = {"apartment": "Flats", "house": "Houses", "room": "Rooms"}
        return icons.get(category_key, "🏠"), labels.get(category_key, category_key)
