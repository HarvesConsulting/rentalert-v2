"""KleinanzeigenParser — HTML-парсер Kleinanzeigen.de.

Обслуговує source 'kleinanzeigen' (DE).
Парсить HTML через BeautifulSoup, метадані — з JSON-LD.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
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


class KleinanzeigenParser(Parser):
    """Парсер Kleinanzeigen.de (DE)."""

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення для міста й категорій."""
        location_id = self.external_id(city)
        if location_id is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        city_slug = city.slug

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
                    city_slug=city_slug,
                    location_id=location_id,
                    category_slug=cat_slug,
                    category_key=cat_key,
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
        location_id: int | str,
        category_slug: str,
        category_key: str,
    ) -> list[Listing]:
        """Завантажує одну категорію."""
        url = f"{self.source.base_url}/s-{category_slug}/{city_slug}/c203l{location_id}"

        human_delay()  # людино-подібна пауза перед запитом

        response = fetch_with_retry(
            cffi_requests.get,
            url,
            impersonate="chrome",
            headers=stealth_headers(),
            timeout=30,
        )

        if response is None:
            log.warning("Kleinanzeigen GET failed після retry")
            return []

        if response.status_code != 200:
            log.warning("Kleinanzeigen %s → HTTP %d", url, response.status_code)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article")

        listings: list[Listing] = []
        for art in articles:
            try:
                lst = self._parse_article(
                    art=art,
                    city_slug=city_slug,
                    category_key=category_key,
                )
                if lst is not None:
                    listings.append(lst)
            except Exception as e:
                log.exception("Помилка парсингу article: %s", e)

        log.info("Kleinanzeigen %s/%s: %d оголошень", city_slug, category_key, len(listings))
        return listings

    def _parse_article(
        self,
        *,
        art: Any,
        city_slug: str,
        category_key: str,
    ) -> Listing | None:
        """Парсить один <article>."""
        ad_id = art.get("data-adid")
        if not ad_id:
            return None

        href = art.get("data-href", "")
        if not href:
            a_tag = art.find("a", href=True)
            href = a_tag["href"] if a_tag else ""
        if not href:
            return None
        url_full = f"{self.source.base_url}{href}" if href.startswith("/") else href

        title, photo, description = self._parse_jsonld(art)

        if not title:
            h3 = art.find("h3")
            if h3:
                title = str(h3.get_text(strip=True))

        if not title:
            return None

        location = self._extract_location(art)
        rooms, _area = self._extract_rooms_area(art)
        price = self._extract_price(art)

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
            created_at=None,
            raw={"description": description[:300] if description else ""},
        )

    # ─────────────────────────────────────────────────────
    # Витягування полів
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_jsonld(art: Any) -> tuple[str, str, str]:
        """Парсить JSON-LD: title, photo, description."""
        json_ld = art.find("script", type="application/ld+json")
        if not json_ld:
            return "", "", ""

        try:
            data = json.loads(json_ld.string or "{}")
        except Exception:
            return "", "", ""

        return (
            str(data.get("title", "") or ""),
            str(data.get("contentUrl", "") or ""),
            str(data.get("description", "") or ""),
        )

    @staticmethod
    def _extract_location(art: Any) -> str:
        r"""Поштовий індекс + місто (regex ^\d{5}\s+\w)."""
        for span in art.find_all("span"):
            text = str(span.get_text(strip=True))
            if re.match(r"^\d{5}\s+\w", text):
                return text
        return ""

    @staticmethod
    def _extract_rooms_area(art: Any) -> tuple[str | None, str | None]:
        """Кімнати (Zi) і площа (m²)."""
        rooms: str | None = None
        area: str | None = None

        for p in art.find_all("p"):
            text = str(p.get_text(strip=True))
            m_area = re.search(r"([\d,]+)\s*m²", text)
            m_rooms = re.search(r"(\d+)\s*Zi", text)
            if m_area:
                area = m_area.group(1).replace(",", ".")
            if m_rooms:
                rooms = m_rooms.group(1)
            if area and rooms:
                break

        return rooms, area

    @staticmethod
    def _extract_price(art: Any) -> str:
        """Перша ціна з €, не перекреслена."""
        for p in art.find_all("p"):
            text = str(p.get_text(strip=True))
            if "€" in text and "line-through" not in " ".join(p.get("class", [])):
                return text
        return ""

    def _category_meta(self, category_key: str) -> tuple[str, str]:
        """Emoji + локалізована назва категорії для DE."""
        icons = {
            "apartment": "🏢",
            "house": "🏠",
            "room": "🚪",
        }
        labels = {
            "apartment": "Wohnungen",
            "house": "Häuser",
            "room": "WG-Zimmer",
        }
        return icons.get(category_key, "🏠"), labels.get(category_key, category_key)
