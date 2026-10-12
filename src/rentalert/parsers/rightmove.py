"""Парсер Rightmove.co.uk — найбільший портал нерухомості UK.

Дані у <script id="__NEXT_DATA__"> → props.pageProps.searchResults.properties

URL: /property-to-rent/find.html?locationIdentifier={id}&index={offset}
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime

from bs4 import BeautifulSoup, Tag
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import (
    fetch_with_retry,
    human_delay,
)

log = logging.getLogger(__name__)

SOURCE_KEY = "rightmove"

# Додай угорі файлу (після SOURCE_KEY)
_IMPERSONATIONS: dict[str, str] = {
    "chrome120": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "chrome124": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "chrome131": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
}

_SEARCH_URL = "https://www.rightmove.co.uk/property-to-rent/find.html"

# Мапінг propertySubType → наша категорія
_PROPERTY_TYPE_MAP = {
    "flat": "apartment",
    "apartment": "apartment",
    "house": "house",
    "detached": "house",
    "semi-detached": "house",
    "terraced": "house",
    "bungalow": "house",
    "maisonette": "apartment",
    "studio": "apartment",
    "room": "room",
    "park-home": "house",
    "land": "house",
}

_CATEGORY_ICONS = {"apartment": "🏢", "house": "🏠", "room": "🚪"}
_CATEGORY_LABELS = {
    "gb": {"apartment": "Flats", "house": "Houses", "room": "Rooms"},
}


class RightmoveParser(Parser):
    """Парсер Rightmove.co.uk."""

    MAX_PAGES = 2
    PAGE_SIZE = 24  # Rightmove повертає 24-25 оголошень

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        location_id = self.external_id(city)
        if not location_id:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        # Rightmove має формат REGION^XXXXX → в URL це REGION%5EXXXXX
        location_identifier = str(location_id)
        if not location_identifier.startswith("REGION"):
            location_identifier = f"REGION^{location_identifier}"

        listings: list[Listing] = []
        seen_ids: set[str] = set()
        import random

        imp_key = random.choice(list(_IMPERSONATIONS.keys()))
        session: cffi_requests.Session = cffi_requests.Session(impersonate=imp_key)
        ua = _IMPERSONATIONS[imp_key]
        log.info("Rightmove %s: impersonate=%s", city.slug, imp_key)

        for page in range(1, self.MAX_PAGES + 1):
            index = (page - 1) * self.PAGE_SIZE
            from urllib.parse import quote

            url = (
                f"{_SEARCH_URL}"
                f"?locationIdentifier={quote(location_identifier, safe='')}"
                f"&index={index}"
                f"&sortType=6"
                f"&includeLetAgreed=false"
            )

            # Rightmove чутливий до rate limit — робимо довші паузи
            human_delay(min_sec=4.0, max_sec=8.0)

            response = fetch_with_retry(
                session.get,
                url,
                headers={
                    "User-Agent": ua,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/avif,image/webp,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Referer": "https://www.rightmove.co.uk/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
                timeout=30,
            )

            if response is None:
                log.warning(
                    "Rightmove %s: сторінка %d → мережа/таймаут",
                    city.slug,
                    page,
                )
                break

            if response.status_code == 403:
                log.error(
                    "Rightmove %s: сторінка %d → HTTP 403 (бан IP). СТОП.",
                    city.slug,
                    page,
                )
                break

            if response.status_code == 429:
                log.error(
                    "Rightmove %s: сторінка %d → HTTP 429 (rate limit). СТОП.",
                    city.slug,
                    page,
                )
                break

            if response.status_code != 200:
                log.warning(
                    "Rightmove %s: сторінка %d → HTTP %s",
                    city.slug,
                    page,
                    response.status_code,
                )
                break

            page_listings = self._parse_page(response.text, city.slug)
            if not page_listings:
                log.info("Rightmove %s: сторінка %d порожня — СТОП", city.slug, page)
                break

            fresh_page: list[Listing] = []
            for lst in page_listings:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    fresh_page.append(lst)

            if not fresh_page:
                log.info("Rightmove %s: сторінка %d — всі дублікати — СТОП", city.slug, page)
                break

            if seen_checker:
                page_ids = [lst.id for lst in fresh_page]
                if seen_checker(page_ids):
                    log.info(
                        "Rightmove %s: сторінка %d — всі вже в БД — СТОП",
                        city.slug,
                        page,
                    )
                    break

            listings.extend(fresh_page)
            log.info(
                "Rightmove %s: сторінка %d — %d оголошень",
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
        search = page_props.get("searchResults", {})
        items = search.get("properties", []) or []

        out: list[Listing] = []
        for item in items:
            lst = self._parse_item(item, city_slug)
            if lst is not None:
                out.append(lst)
        return out

    def _parse_item(self, item: dict, city_slug: str) -> Listing | None:
        item_id = item.get("id")
        if not item_id:
            return None

        listing_id = self.make_id(item_id)

        # URL: propertyUrl = "/properties/90327186#/?channel=RES_LET"
        href = item.get("propertyUrl", "")
        if href:
            # Прибираємо hash і query
            href = href.split("#")[0]
            if not href.startswith("http"):
                href = f"{self.source.base_url}{href}"

        # Ціна
        price = "—"
        price_obj = item.get("price") or {}
        if isinstance(price_obj, dict):
            amount = price_obj.get("amount")
            currency = price_obj.get("currencyCode", "GBP")
            frequency = price_obj.get("frequency", "")
            if amount:
                price = f"{amount} {currency}"
                if frequency:
                    price += f" / {frequency}"

        # Адреса
        location = (item.get("displayAddress") or "").replace("\n", ", ").strip(", ")
        # "Pentonville Road, Angel, N1" → нормалізуємо
        location = " ".join(location.split())

        # Кімнати
        bedrooms = item.get("bedrooms")
        rooms = str(bedrooms) if bedrooms is not None else None

        # Площа
        display_size = item.get("displaySize", "")
        area_m2 = self._parse_size(display_size)

        # Категорія
        subtype = (item.get("propertySubType") or "").lower()
        category = self._classify(subtype, item.get("propertyTypeFullDescription", ""))

        icon = _CATEGORY_ICONS.get(category, "🏠")
        label_map = _CATEGORY_LABELS.get(self.source.country, {})
        label = label_map.get(category, category)

        # Фото
        photo = ""
        images_obj = item.get("propertyImages") or {}
        if isinstance(images_obj, dict):
            main = images_obj.get("mainImageSrc", "")
            if main:
                photo = main
            else:
                imgs = images_obj.get("images") or []
                if imgs and isinstance(imgs[0], dict):
                    photo = imgs[0].get("srcUrl", "")

        # Дата
        created_at = self._parse_date(item)

        return Listing(
            id=listing_id,
            source_key=self.source.key,
            city_slug=city_slug,
            title=item.get("propertyTypeFullDescription", "") or item.get("summary", "")[:100],
            price=price,
            location=location,
            link=href,
            photo=photo,
            rooms=rooms,
            area_m2=area_m2,
            category=category,
            category_icon=icon,
            category_label=label,
            created_at=created_at,
            raw=item,
        )

    @staticmethod
    def _classify(subtype: str, full_desc: str) -> str:
        """Визначає категорію: apartment / house / room."""
        text = f"{subtype} {full_desc}".lower()
        for key, cat in _PROPERTY_TYPE_MAP.items():
            if key in text:
                return cat
        return "apartment"

    @staticmethod
    def _parse_size(display_size: str) -> float | None:
        """'361 sq. ft.' → 33.5 (м²). 1 sq.ft = 0.0929 м²."""
        if not display_size:
            return None
        import re

        m = re.search(r"([\d,\.]+)\s*sq\.?\s*ft", display_size, re.IGNORECASE)
        if m:
            try:
                sqft = float(m.group(1).replace(",", ""))
                return round(sqft * 0.0929, 1)
            except ValueError:
                return None

        m = re.search(r"([\d,\.]+)\s*sq\.?\s*m", display_size, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                return None

        return None

    @staticmethod
    def _parse_date(item: dict) -> datetime | None:
        """firstVisibleDate: "2026-06-30T18:00:55Z"."""
        raw = item.get("firstVisibleDate") or item.get("updateDate")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
