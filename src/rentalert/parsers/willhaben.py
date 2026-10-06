"""Willhaben.at — HTML/JSON-парсер.

Willhaben — австрійський класифайдс.
Дані лежать у `<script id="__NEXT_DATA__">` (Next.js).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import (
    fetch_with_retry,
    human_delay,
    stealth_headers,
)

log = logging.getLogger(__name__)


class WillhabenParser(Parser):
    """Парсер Willhaben.at (Австрія)."""

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        location_slug = self.external_id(city)
        if not location_slug:
            log.warning("City %r не має refs для willhaben", city.slug)
            return []

        category_urls = self.source.config.get("category_urls", {})
        if not category_urls:
            log.warning("Source willhaben не має category_urls")
            return []

        all_listings: list[Listing] = []
        seen_ids: set[str] = set()

        for cat_key in categories:
            if not self.supports_category(cat_key):
                continue

            cat_path = category_urls.get(cat_key)
            if not cat_path:
                continue

            try:
                batch = self._fetch_category(
                    city_slug=city.slug,
                    location_slug=str(location_slug),
                    category_path=cat_path,
                    category_key=cat_key,
                    seen_checker=seen_checker,
                )
            except Exception as e:
                log.exception("Willhaben %s/%s: %s", city.slug, cat_key, e)
                continue

            for lst in batch:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    all_listings.append(lst)

        return all_listings

    # ─────────────────────────────────────────────────────
    # Внутрішнє
    # ─────────────────────────────────────────────────────

    MAX_PAGES = 3

    def _fetch_category(
        self,
        *,
        city_slug: str,
        location_slug: str,
        category_path: str,
        category_key: str,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує одну категорію (з пагінацією)."""
        all_listings: list[Listing] = []
        seen_in_run: set[str] = set()

        for page in range(1, self.MAX_PAGES + 1):
            url = f"{self.source.base_url}/{category_path}/{location_slug}"
            params = {"page": page} if page > 1 else None

            human_delay()

            response = fetch_with_retry(
                cffi_requests.get,
                url,
                params=params,
                impersonate="chrome",
                headers=stealth_headers(),
                timeout=30,
            )

            if response is None or response.status_code != 200:
                log.warning(
                    "Willhaben %s/%s page=%d → HTTP %s",
                    city_slug,
                    category_key,
                    page,
                    response.status_code if response else "None",
                )
                break

            items = self._extract_items(response.text)
            if not items:
                log.info(
                    "Willhaben %s/%s page=%d — порожньо — СТОП",
                    city_slug,
                    category_key,
                    page,
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
                log.info("Willhaben %s/%s — всі дублі — СТОП", city_slug, category_key)
                break

            # Перевірка, чи всі вже в БД
            if seen_checker:
                page_ids = [lst.id for lst in page_listings]
                if seen_checker(page_ids):
                    log.info(
                        "Willhaben %s/%s page=%d — всі в БД — СТОП",
                        city_slug,
                        category_key,
                        page,
                    )
                    break

            all_listings.extend(page_listings)
            log.info(
                "Willhaben %s/%s page=%d — %d оголошень",
                city_slug,
                category_key,
                page,
                len(page_listings),
            )

        return all_listings

    def _extract_items(self, html: str) -> list[dict[str, Any]]:
        """Витягує advertSummary з __NEXT_DATA__."""
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script is None:
            return []

        # mypy: script.string може бути None
        script_text = getattr(script, "string", None)
        if not script_text:
            return []

        try:
            data = json.loads(script_text)
        except Exception as e:
            log.exception("JSON parse error: %s", e)
            return []

        # Шлях: props.pageProps.searchResult.advertSummaryList.advertSummary
        try:
            summary = (
                data.get("props", {})
                .get("pageProps", {})
                .get("searchResult", {})
                .get("advertSummaryList", {})
                .get("advertSummary", [])
            )
            return summary or []
        except Exception as e:
            log.exception("Path error: %s", e)
            return []

    def _parse_item(
        self,
        *,
        item: dict[str, Any],
        city_slug: str,
        category_key: str,
    ) -> Listing | None:
        """Парсить один advertSummary → Listing."""
        item_id = item.get("id")
        if not item_id:
            return None

        # adTypeId = 2 → оренда (фільтруємо продаж)
        if item.get("adTypeId") not in (2, None):
            return None

        # Витягуємо attributes у dict
        attrs = self._attrs_to_dict(item.get("attributes", {}).get("attribute", []))

        title = attrs.get("HEADING", "") or item.get("description", "")
        if not title:
            return None

        price = attrs.get("PRICE_FOR_DISPLAY", "") or attrs.get("PRICE", "")
        location = self._format_location(attrs)
        rooms = attrs.get("NUMBER_OF_ROOMS") or attrs.get("ROOMS")
        photo = self._extract_photo(item)
        link = self._format_link(attrs)
        created_at = self._parse_date(attrs.get("PUBLISHED_String"))

        category_icon, category_label = self._category_meta(category_key)

        return Listing(
            id=self.make_id(item_id),
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price or "—",
            location=location,
            link=link,
            photo=photo,
            rooms=rooms,
            area_m2=None,
            category=category_key,
            category_icon=category_icon,
            category_label=category_label,
            created_at=created_at,
            raw=item,
        )

    @staticmethod
    def _attrs_to_dict(attrs: list[dict[str, Any]]) -> dict[str, str]:
        """Перетворює [{name, values}] → {name: first_value}."""
        result: dict[str, str] = {}
        for attr in attrs:
            name = attr.get("name")
            values = attr.get("values", [])
            if name and values:
                result[name] = values[0]
        return result

    @staticmethod
    def _format_location(attrs: dict[str, str]) -> str:
        """Формує 'Postcode Location, District'."""
        postcode = attrs.get("POSTCODE", "")
        location = attrs.get("LOCATION", "")
        district = attrs.get("DISTRICT", "")

        parts = []
        if postcode and location:
            parts.append(f"{postcode} {location}")
        elif location:
            parts.append(location)
        if district and district != location:
            parts.append(district)

        return ", ".join(parts)

    def _format_link(self, attrs: dict[str, str]) -> str:
        """Формує повний URL з SEO_URL."""
        seo_url = attrs.get("SEO_URL", "")
        if not seo_url:
            return ""
        base_url: str = self.source.base_url
        return f"{base_url}/iad/{seo_url}"

    @staticmethod
    def _extract_photo(item: dict[str, Any]) -> str:
        """Бере перше фото з advertImageList."""
        images = item.get("advertImageList", {}).get("advertImage", [])
        if not images:
            return ""
        first = images[0]
        if isinstance(first, dict):
            url: str = first.get("mainImageUrl", "") or first.get("referenceImageUrl", "")
            return str(url)
        return ""

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        """Парсить ISO-дату."""
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Emoji + локалізована назва."""
        icons = {
            "apartment": "🏢",
            "house": "🏠",
            "room": "🚪",
        }
        labels = {
            "apartment": "Wohnungen",
            "house": "Häuser",
            "room": "Zimmer",
        }
        return icons.get(category_key, "🏠"), labels.get(category_key, category_key)
