"""Парсер Wikicasa.it — італійський портал нерухомості.

Картки: <article data-cy="real-estate-insertion" data-id="..." data-url="/annuncio/...">

URL: https://www.wikicasa.it/affitto-case/{city_slug}/
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime

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

SOURCE_KEY = "wikicasa"

_SEARCH_URL = "https://www.wikicasa.it/affitto-case/{slug}/"

_ROOMS_RE = re.compile(r"(\d+)")
_SQM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

_CATEGORY_ICONS = {"apartment": "🏢", "house": "🏠", "room": "🚪"}
_CATEGORY_LABELS = {
    "it": {"apartment": "Appartamenti", "house": "Case", "room": "Stanze"},
}


class WikicasaParser(Parser):
    """Парсер Wikicasa.it."""

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
                url += f"?p={page}"

            human_delay()

            response = fetch_with_retry(
                session.get,
                url,
                headers=stealth_headers(
                    {
                        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
                        "Referer": "https://www.wikicasa.it/",
                    }
                ),
                timeout=30,
            )

            if response is None or response.status_code != 200:
                log.warning(
                    "Wikicasa %s: сторінка %d → HTTP %s",
                    city.slug,
                    page,
                    response.status_code if response else "None",
                )
                break

            page_listings = self._parse_page(response.text, city.slug)
            if not page_listings:
                log.info("Wikicasa %s: сторінка %d порожня — СТОП", city.slug, page)
                break

            fresh_page: list[Listing] = []
            for lst in page_listings:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    fresh_page.append(lst)

            if not fresh_page:
                log.info("Wikicasa %s: сторінка %d — всі дублікати — СТОП", city.slug, page)
                break

            if seen_checker:
                page_ids = [lst.id for lst in fresh_page]
                if seen_checker(page_ids):
                    log.info(
                        "Wikicasa %s: сторінка %d — всі вже в БД — СТОП",
                        city.slug,
                        page,
                    )
                    break

            listings.extend(fresh_page)
            log.info(
                "Wikicasa %s: сторінка %d — %d оголошень",
                city.slug,
                page,
                len(fresh_page),
            )

        return listings

    def _parse_page(self, html: str, city_slug: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select('article[data-cy="real-estate-insertion"]')

        out: list[Listing] = []
        for card in cards:
            lst = self._parse_card(card, city_slug)
            if lst is not None:
                out.append(lst)
        return out

    def _parse_card(self, card: Tag, city_slug: str) -> Listing | None:
        item_id = card.get("data-id")
        if not item_id or not isinstance(item_id, str):
            return None

        listing_id = self.make_id(item_id)

        # URL
        href = card.get("data-url", "")
        if not isinstance(href, str):
            href = ""
        if href and not href.startswith("http"):
            href = f"{self.source.base_url}{href}"

        # Ціна
        price = ""
        price_el = card.select_one(".price")
        if price_el:
            text = price_el.get_text(strip=True)
            if text:
                price = text

        # Заголовок
        title = ""
        title_el = card.select_one('.title-link, [data-cy="insertion-real-estate-title"]')
        if isinstance(title_el, Tag):
            raw_title = title_el.get("title", "")
            if isinstance(raw_title, str) and raw_title:
                title = raw_title
            else:
                title = title_el.get_text(strip=True)

        # Локація
        location = ""
        title_row = card.select_one(".title-row")
        if isinstance(title_row, Tag):
            spans = title_row.find_all("span")
            if len(spans) >= 2:
                location = spans[-1].get_text(strip=True)

        # Кімнати
        rooms: str | None = None
        rooms_el = card.select_one(".redi-rooms-section")
        if isinstance(rooms_el, Tag):
            m = _ROOMS_RE.search(rooms_el.get_text(" ", strip=True))
            if m:
                rooms = m.group(1)

        # Площа
        area_m2: float | None = None
        sqm_el = card.select_one(".redi-sqm-section")
        if isinstance(sqm_el, Tag):
            m = _SQM_RE.search(sqm_el.get_text(" ", strip=True))
            if m:
                with contextlib.suppress(ValueError):
                    area_m2 = float(m.group(1).replace(",", "."))

        # Фото
        photo = ""
        img = card.find("img")
        if isinstance(img, Tag):
            raw_src = img.get("src", "")
            if isinstance(raw_src, str):
                photo = raw_src

        # Дата
        created_at = None
        badge = card.select_one('[data-cy="badges-container"] .uikit-badge')
        if isinstance(badge, Tag):
            badge_text = badge.get_text(" ", strip=True).lower()
            if "novità" in badge_text or "nuovo" in badge_text:
                created_at = datetime.now(UTC)

        # Категорія
        category = "apartment"
        icon = _CATEGORY_ICONS.get(category, "🏠")
        label_map = _CATEGORY_LABELS.get(self.source.country, {})
        label = label_map.get(category, category)

        return Listing(
            id=listing_id,
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price or "—",
            location=location,
            link=href,
            photo=photo,
            rooms=rooms,
            area_m2=area_m2,
            category=category,
            category_icon=icon,
            category_label=label,
            created_at=created_at,
            raw={"data_id": item_id},
        )
