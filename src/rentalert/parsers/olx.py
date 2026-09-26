"""OLXParser — парсер усіх OLX-сайтів.

Обслуговує olx_ua, olx_pl, olx_pt, olx_ro, olx_bg.
Різниця між ними — у base_url і category_ids (з config).
"""

from __future__ import annotations

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


class OLXParser(Parser):
    """Парсер OLX (усі країни).

    Використовує публічний API: {base_url}/api/v1/offers/
    """

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        external_id = self.external_id(city)
        if external_id is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        category_ids = self.source.config.get("category_ids", {})
        if not category_ids:
            log.warning("Source %r не має config.category_ids", self.source.key)
            return []

        # PT використовує region_id, решта — city_id
        is_portugal = self.source.country == "pt"
        location_param = "region_id" if is_portugal else "city_id"

        listings: list[Listing] = []
        seen_ids: set[str] = set()

        for cat_key in categories:
            if not self.supports_category(cat_key):
                continue

            cat_id = category_ids.get(cat_key)
            if cat_id is None:
                log.warning("Category %r не має ID у %r", cat_key, self.source.key)
                continue

            try:
                batch = self._fetch_category(
                    location_param=location_param,
                    location_id=external_id,
                    category_id=cat_id,
                    category_key=cat_key,
                    city_slug=city.slug,
                    seen_checker=seen_checker,
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

    MAX_PAGES = 5  # запобіжник від зациклення

    def _fetch_category(
        self,
        *,
        location_param: str,
        location_id: int | str,
        category_id: int,
        category_key: str,
        city_slug: str,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує одну категорію (з пагінацією)."""
        all_listings: list[Listing] = []
        seen_in_run: set[str] = set()
        offset = 0

        session: cffi_requests.Session = cffi_requests.Session(impersonate="chrome")

        for page in range(1, self.MAX_PAGES + 1):
            params = {
                "offset": offset,
                "limit": 40,
                location_param: location_id,
                "category_id": category_id,
                "sort_by": "created_at:desc",
            }

            human_delay()

            response = fetch_with_retry(
                session.get,
                f"{self.source.base_url}/api/v1/offers/",
                params=params,
                headers=stealth_headers(),
                timeout=30,
            )

            if response is None or response.status_code != 200:
                log.warning(
                    "OLX %s/%s offset=%d → HTTP %s",
                    city_slug,
                    category_key,
                    offset,
                    response.status_code if response else "None",
                )
                break

            data = response.json()
            items = data.get("data", []) or []

            if not items:
                log.info(
                    "OLX %s/%s: offset=%d — порожня сторінка — СТОП",
                    city_slug,
                    category_key,
                    offset,
                )
                break

            page_listings: list[Listing] = []
            for item in items:
                try:
                    lst = self._parse_item(
                        item=item,
                        city_slug=city_slug,
                        category_key=category_key,
                    )
                    if lst is not None and lst.id not in seen_in_run:
                        seen_in_run.add(lst.id)
                        page_listings.append(lst)
                except Exception as e:
                    log.exception("Помилка парсингу item: %s", e)

            if not page_listings:
                log.info(
                    "OLX %s/%s: offset=%d — всі дублікати — СТОП",
                    city_slug,
                    category_key,
                    offset,
                )
                break

            # Перевірка: чи всі вже в БД?
            if seen_checker:
                page_ids = [lst.id for lst in page_listings]
                if seen_checker(page_ids):
                    log.info(
                        "OLX %s/%s: offset=%d — всі вже в БД — СТОП",
                        city_slug,
                        category_key,
                        offset,
                    )
                    break

            all_listings.extend(page_listings)
            log.info(
                "OLX %s/%s: сторінка %d (offset=%d) — %d оголошень",
                city_slug,
                category_key,
                page,
                offset,
                len(page_listings),
            )

            offset += 52  # OLX повертає 52 за один запит

        return all_listings

    def _parse_item(
        self,
        *,
        item: dict[str, Any],
        city_slug: str,
        category_key: str,
    ) -> Listing | None:
        """Парсить один item з OLX API."""
        item_id = item.get("id")
        if not item_id:
            return None

        title = item.get("title", "") or ""

        # ── Фільтр для Португалії: тільки оренда ──
        # OLX.pt API не підтримує параметр фільтру за орендою,
        # тому фільтруємо за заголовком.
        if self.source.country == "pt":
            title_lower = title.lower()
            sale_markers = (
                "venda",
                "vender",
                "à venda",
                "para venda",
                "comprar",
                "compra",
                "vendido",
                "vendida",
            )
            if any(marker in title_lower for marker in sale_markers):
                return None  # пропускаємо продаж

        url = item.get("url", "") or ""
        if url and not url.startswith("http"):
            url = f"{self.source.base_url}{url}"

        price_label = self._extract_price(item)
        location_str = self._extract_location(item)
        rooms = self._extract_rooms(item)
        photo = self._extract_photo(item)
        created_at = self._extract_created_at(item)

        category_icon, category_label = self._category_meta(category_key)

        return Listing(
            id=self.make_id(item_id),
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price_label or "—",
            location=location_str,
            link=url,
            photo=photo,
            rooms=rooms,
            category=category_key,
            category_icon=category_icon,
            category_label=category_label,
            created_at=created_at,
            raw=item,
        )

    # ─────────────────────────────────────────────────────
    # Витягування полів
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_price(item: dict[str, Any]) -> str:
        for param in item.get("params", []) or []:
            if param.get("key") == "price":
                value = param.get("value", {})
                if isinstance(value, dict):
                    return value.get("label", "") or ""
        return ""

    @staticmethod
    def _extract_location(item: dict[str, Any]) -> str:
        loc = item.get("location", {}) or {}
        if not isinstance(loc, dict):
            return ""
        city = loc.get("city") or {}
        region = loc.get("region") or {}
        city_name = city.get("name", "") if isinstance(city, dict) else ""
        region_name = region.get("name", "") if isinstance(region, dict) else ""
        if region_name:
            return f"{city_name}, {region_name}" if city_name else region_name
        return city_name or ""

    @staticmethod
    def _extract_rooms(item: dict[str, Any]) -> str | None:
        for param in item.get("params", []) or []:
            key = param.get("key", "").lower()
            name = param.get("name", "").lower()
            if "room" in key or "кімнат" in name or "quarto" in name:
                value = param.get("value", {})
                if isinstance(value, dict):
                    raw = value.get("key") or value.get("label")
                elif value:
                    raw = str(value)
                else:
                    raw = None
                if raw:
                    return str(raw)
        return None

    @staticmethod
    def _extract_photo(item: dict[str, Any]) -> str:
        photos = item.get("photos", []) or []
        if not photos or not isinstance(photos, list):
            return ""
        first = photos[0]
        if not isinstance(first, dict):
            return ""
        url = first.get("link", "") or ""
        if url and "{width}" in url:
            url = url.replace("{width}", "1000").replace("{height}", "750")
        return url

    @staticmethod
    def _extract_created_at(item: dict[str, Any]) -> datetime | None:
        raw = item.get("created_time") or item.get("last_refresh_time") or ""
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Повертає (icon, label) для категорії.

        Джерело даних — CATEGORY_KEYS_* у v1, тепер — у нас всередині.
        У майбутньому — перенесемо в Source.config.
        """
        # Просте мапування (можна винести у JSON)
        icons = {
            "apartment": "🏢",
            "house": "🏠",
            "room": "🚪",
            "daily": "🌙",
        }
        labels_by_country = {
            "ua": {
                "apartment": "Квартири",
                "house": "Будинки",
                "room": "Кімнати",
                "daily": "Подобова",
            },
            "pl": {
                "apartment": "Mieszkania",
                "house": "Domy",
                "room": "Pokoje",
            },
            "pt": {
                "apartment": "Apartamentos",
                "house": "Moradias",
                "room": "Quartos",
            },
            "ro": {
                "apartment": "Apartamente",
                "house": "Case",
            },
            "bg": {
                "apartment": "Апартаменти",
                "house": "Къщи",
            },
        }
        icon = icons.get(category_key, "🏠")
        labels = labels_by_country.get(self.source.country, {})
        label = labels.get(category_key, category_key)
        return icon, label
