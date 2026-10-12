"""Парсер Otodom.pl — найбільший портал нерухомості Польщі (OLX Group).

Дані у <script id="__NEXT_DATA__"> як JSON.

URL: /pl/wyniki/wynajem/mieszkanie/{voivodeship}/{city}/{city}/{city}
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import (
    fetch_with_retry,
    human_delay,
    stealth_headers,
)

log = logging.getLogger(__name__)

SOURCE_KEY = "otodom_pl"

_SEARCH_URL = "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/{slug}"

_ROOMS_MAP = {
    "ONE": "1",
    "TWO": "2",
    "THREE": "3",
    "FOUR": "4",
    "FIVE": "5",
    "SIX": "6",
    "SEVEN": "7",
    "EIGHT": "8",
    "NINE": "9",
    "TEN": "10",
}

_ESTATE_MAP = {
    "FLAT": "apartment",
    "HOUSE": "house",
    "ROOM": "room",
}

_CATEGORY_ICONS = {"apartment": "🏢", "house": "🏠", "room": "🚪"}
_CATEGORY_LABELS = {
    "pl": {"apartment": "Mieszkania", "house": "Domy", "room": "Pokoje"},
}


class OtodomParser(Parser):
    """Парсер Otodom.pl."""

    MAX_PAGES = 5

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        slug = self.external_id(city)
        if not slug:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        listings: list[Listing] = []
        seen_ids: set[str] = set()

        session: cffi_requests.Session = cffi_requests.Session(impersonate="chrome124")

        for page in range(1, self.MAX_PAGES + 1):
            url = _SEARCH_URL.format(slug=slug)
            if page > 1:
                url += f"?page={page}"

            human_delay()

            response = fetch_with_retry(
                session.get,
                url,
                headers=stealth_headers(
                    {
                        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
                        "Referer": "https://www.otodom.pl/",
                    }
                ),
                timeout=30,
            )

            if response is None or response.status_code != 200:
                log.warning(
                    "Otodom %s: сторінка %d → HTTP %s",
                    city.slug,
                    page,
                    response.status_code if response else "None",
                )
                break

            page_listings = self._parse_page(response.text, city.slug)
            if not page_listings:
                log.info("Otodom %s: сторінка %d порожня — СТОП", city.slug, page)
                break

            fresh_page: list[Listing] = []
            for lst in page_listings:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    fresh_page.append(lst)

            if not fresh_page:
                log.info("Otodom %s: сторінка %d — всі дублікати — СТОП", city.slug, page)
                break

            if seen_checker:
                page_ids = [lst.id for lst in fresh_page]
                if seen_checker(page_ids):
                    log.info(
                        "Otodom %s: сторінка %d — всі вже в БД — СТОП",
                        city.slug,
                        page,
                    )
                    break

            listings.extend(fresh_page)
            log.info(
                "Otodom %s: сторінка %d — %d оголошень",
                city.slug,
                page,
                len(fresh_page),
            )

        return listings

    def _parse_page(self, html: str, city_slug: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not isinstance(script, Tag):
            return []

        raw_json = script.string
        if not isinstance(raw_json, str):
            return []

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return []

        page_props = data.get("props", {}).get("pageProps", {})
        items = self._find_items(page_props) or []

        out: list[Listing] = []
        for item in items:
            lst = self._parse_item(item, city_slug)
            if lst is not None:
                out.append(lst)
        return out

    @staticmethod
    def _find_items(obj: Any, depth: int = 0) -> list[dict] | None:
        if depth > 8:
            return None
        if isinstance(obj, dict):
            if "items" in obj and isinstance(obj["items"], list):
                return obj["items"]
            for v in obj.values():
                r = OtodomParser._find_items(v, depth + 1)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for it in obj[:5]:
                r = OtodomParser._find_items(it, depth + 1)
                if r is not None:
                    return r
        return None

    def _parse_item(self, item: dict, city_slug: str) -> Listing | None:
        if item.get("transaction") != "RENT":
            return None

        item_id = item.get("id")
        if not item_id:
            return None

        listing_id = self.make_id(item_id)

        href = item.get("href", "")
        if href:
            href = href.replace("[lang]", "pl")
            if href and not href.startswith("/"):
                href = "/" + href
            if not href.startswith("http"):
                href = f"{self.source.base_url}{href}"

        # Ціна
        price = "—"
        total = item.get("totalPrice")
        if isinstance(total, dict) and total.get("value"):
            currency = total.get("currency", "PLN")
            price = f"{total['value']} {currency}"

        # Кімнати
        rooms_raw = item.get("roomsNumber")
        rooms = _ROOMS_MAP.get(rooms_raw) if rooms_raw else None

        # Площа
        area = item.get("areaInSquareMeters")

        # Локація — Otodom має address.city = null, треба reverseGeocoding
        location_str = self._extract_location(item)

        # Категорія
        estate = item.get("estate", "")
        category = _ESTATE_MAP.get(estate, "apartment")
        icon = _CATEGORY_ICONS.get(category, "🏠")
        label_map = _CATEGORY_LABELS.get(self.source.country, {})
        label = label_map.get(category, category)

        # Фото
        images = item.get("images") or []
        photo = ""
        if images and isinstance(images[0], dict):
            photo = images[0].get("medium", "") or images[0].get("small", "")

        created_at = self._parse_date(item)

        return Listing(
            id=listing_id,
            source_key=self.source.key,
            city_slug=city_slug,
            title=item.get("title", "") or "",
            price=price,
            location=location_str,
            link=href,
            photo=photo,
            rooms=rooms,
            area_m2=float(area) if area else None,
            category=category,
            category_icon=icon,
            category_label=label,
            created_at=created_at,
            raw=item,
        )

    @staticmethod
    def _extract_location(item: dict) -> str:
        """Витягує локацію. Otodom: address.city = null, тому беремо з reverseGeocoding."""
        loc = item.get("location", {})
        if not isinstance(loc, dict):
            return ""

        # 1. Проба з address (може бути null)
        address = loc.get("address") or {}
        if isinstance(address, dict):
            city_name = (address.get("city") or {}).get("name", "") if address.get("city") else ""
            province_name = (
                (address.get("province") or {}).get("name", "") if address.get("province") else ""
            )
            if city_name or province_name:
                return ", ".join(filter(None, [city_name, province_name]))

        # 2. Fallback: reverseGeocoding.locations
        rev = loc.get("reverseGeocoding") or {}
        locations = rev.get("locations") if isinstance(rev, dict) else None
        if not isinstance(locations, list):
            return ""

        parts: list[str] = []
        for level in locations:
            if not isinstance(level, dict):
                continue
            lvl = level.get("locationLevel", "")
            name = level.get("name", "")
            if not name:
                continue
            # Пріоритет: city_or_village → district → voivodeship
            if lvl == "city_or_village" or lvl == "district" or lvl == "voivodeship":
                parts.append(name)

        return ", ".join(parts)

    @staticmethod
    def _parse_date(item: dict) -> datetime | None:
        """dateCreated: "2026-09-06T13:32:13Z" (ISO з T і Z)."""
        raw = item.get("dateCreated")
        if not raw:
            return None
        try:
            # Замінюємо Z на +00:00 для fromisoformat
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
