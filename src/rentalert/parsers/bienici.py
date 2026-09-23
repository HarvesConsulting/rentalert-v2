"""BienIciParser — парсер Bien'ici.com (Франція).

Обслуговує source 'bienici' (FR).

Bien'ici має JSON API:
- GET https://www.bienici.com/realEstateAds.json
- Параметри: filters (JSON), extensionType
- Повертає: realEstateAds (список оголошень)

Фільтр по місту — через zoneIdsByTypes.zoneIds (zoneId з fr.json).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import (
    fetch_with_retry,
    human_delay,
    stealth_headers,
)

log = logging.getLogger(__name__)


# Категорія → propertyType Bien'ici
_PROPERTY_TYPES: dict[str, str] = {
    "apartment": "flat",
    "house": "house",
}


class BienIciParser(Parser):
    """Парсер Bien'ici.com (FR)."""

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        zone_id = self.external_id(city)
        if zone_id is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        listings: list[Listing] = []
        seen_ids: set[str] = set()

        for cat_key in categories:
            if not self.supports_category(cat_key):
                continue

            property_type = _PROPERTY_TYPES.get(cat_key)
            if not property_type:
                log.warning("Категорія %r не підтримується Bien'ici", cat_key)
                continue

            try:
                batch = self._fetch_category(
                    zone_id=str(zone_id),
                    property_type=property_type,
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
        zone_id: str,
        property_type: str,
        category_key: str,
        city: City,
    ) -> list[Listing]:
        """Завантажує одну категорію."""
        filters = {
            "size": 500,
            "from": 0,
            "filterType": "rent",
            "propertyType": [property_type],
            "page": 1,
            "sortBy": "relevance",
            "sortOrder": "desc",
            "onTheMarket": [True],
            "zoneIdsByTypes": {"zoneIds": [zone_id]},
        }

        url = f"{self.source.base_url}/realEstateAds.json"

        human_delay()  # пауза перед запитом

        response = fetch_with_retry(
            cffi_requests.get,
            url,
            params={
                "filters": json.dumps(filters),
                "extensionType": "extendedIfNoResult",
            },
            impersonate="chrome",
            headers=stealth_headers(),
            timeout=30,
        )

        if response is None or response.status_code != 200:
            log.warning(
                "Bien'ici %s/%s → HTTP %s",
                city.slug,
                category_key,
                response.status_code if response else "None",
            )
            return []

        try:
            data = response.json()
        except Exception as e:
            log.warning("Bien'ici %s: неправильний JSON: %s", city.slug, e)
            return []

        items = data.get("realEstateAds", []) or []
        log.info(
            "Bien'ici %s/%s: %d оголошень (total=%s)",
            city.slug,
            category_key,
            len(items),
            data.get("total"),
        )

        listings: list[Listing] = []
        for item in items:
            try:
                lst = self._parse_item(
                    item=item,
                    city_slug=city.slug,
                    category_key=category_key,
                )
                if lst is not None:
                    listings.append(lst)
            except Exception as e:
                log.exception("Помилка парсингу item: %s", e)

        return listings

    def _parse_item(
        self,
        *,
        item: dict[str, Any],
        city_slug: str,
        category_key: str,
    ) -> Listing | None:
        """Парсить один item з Bien'ici API."""
        item_id = item.get("id")
        if not item_id:
            return None

        title = (item.get("title") or "").strip()
        description = (item.get("description") or "")[:200]

        # Якщо title порожній — беремо перше речення з description
        if not title and description:
            title = description.split(".")[0][:100]

        if not title:
            return None

        # Ціна
        price_raw = item.get("price", 0)
        if isinstance(price_raw, (int, float)) and price_raw > 0:
            price = f"{int(price_raw)} €"
        else:
            price = "—"

        # Локація
        city_name = item.get("city") or ""
        postal = item.get("postalCode") or ""
        district = (item.get("district") or {}).get("libelle") or ""
        location_parts = [p for p in [city_name, postal, district] if p]
        location = ", ".join(location_parts)

        # Кімнати / площа
        rooms = item.get("roomsQuantity")
        area = item.get("surfaceArea")

        # Фото
        photo = ""
        photos = item.get("photos") or []
        if photos and isinstance(photos, list):
            first = photos[0]
            if isinstance(first, dict):
                photo = first.get("url") or ""

        # Посилання
        link = f"{self.source.base_url}/annonce/{item_id}"

        # Дата
        created_at = self._extract_date(item)

        icon, label = self._category_meta(category_key)

        return Listing(
            id=self.make_id(item_id),
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price,
            location=location,
            link=link,
            photo=photo,
            rooms=str(rooms) if rooms else None,
            category=category_key,
            category_icon=icon,
            category_label=label,
            created_at=created_at,
            raw={
                "description": description,
                "area": area,
                "property_type": item.get("propertyType"),
            },
        )

    # ─────────────────────────────────────────────────────
    # Витягування полів
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_date(item: dict[str, Any]) -> datetime | None:
        """Витягує дату публікації/оновлення."""
        raw = item.get("publicationDate") or item.get("modificationDate") or ""
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            # 1970 — означає "невідомо"
            if dt.year == 1970:
                return None
            return dt
        except Exception:
            return None

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Emoji + локалізована назва категорії для FR."""
        icons = {
            "apartment": "🏢",
            "house": "🏠",
        }
        labels = {
            "apartment": "Appartements",
            "house": "Maisons",
        }
        return icons.get(category_key, "🏠"), labels.get(category_key, category_key)
