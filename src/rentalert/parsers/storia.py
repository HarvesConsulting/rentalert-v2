"""StoriaParser — парсер Storia.ro (Румунія).

Сайт — Next.js (SSR), картки рендеряться сервером.
Капчі немає при curl_cffi з impersonate="chrome124".

ID оголошення — у URL: /ro/oferta/...-ID<XXXX>.html
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

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

SOURCE_KEY = "storia_ro"

_SEARCH_URL = "https://www.storia.ro/ro/rezultate/inchiriere/apartament/{slug}"

# ID у посиланні: "...-IDIPJx" або "...-IDIO18.html" (з розширенням або без)
_ID_RE = re.compile(r"-ID([A-Za-z0-9]+)(?:\.html)?$")

# Площа: "35 m²" або "123,5 m²"
_AREA_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m²")

# Кімнати: "1 cameră", "3 camere"
_ROOMS_RE = re.compile(r"(\d+)\s*camer")

# Поверх: "parter" або "etajul 4"
_FLOOR_RE = re.compile(r"^(parter|etajul\s+\d+)$", re.IGNORECASE)

# "Adăugat astăzi" — окремо
_POSTED_TODAY_RE = re.compile(r"ad[ăa]ugat\s+ast[ăa]zi", re.IGNORECASE)
# "Adăugat acum N zile/ore/minute"
_POSTED_AGO_RE = re.compile(
    r"ad[ăa]ugat\s+acum\s+(\d+)\s+(zi|zile|ore|minute)",
    re.IGNORECASE,
)
# "Reactualizat" — продавець оновив оголошення
_REACTUALIZAT_RE = re.compile(r"reactualizat", re.IGNORECASE)


class StoriaParser(Parser):
    """Парсер Storia.ro."""

    MAX_PAGES = 5

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        if not self.supports_category("apartment"):
            return []
        if "apartment" not in categories:
            return []

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
                        "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
                        "Referer": "https://www.storia.ro/",
                        "Sec-Fetch-Site": "same-origin",
                    }
                ),
                timeout=30,
            )

            if response is None or response.status_code != 200:
                log.warning(
                    "Storia %s: сторінка %d → HTTP %s",
                    city.slug,
                    page,
                    response.status_code if response else "None",
                )
                break

            page_listings = self._parse_page(response.text, city.slug)
            if not page_listings:
                log.info("Storia %s: сторінка %d порожня — СТОП", city.slug, page)
                break

            fresh_page: list[Listing] = []
            for lst in page_listings:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    fresh_page.append(lst)

            if not fresh_page:
                log.info("Storia %s: сторінка %d — всі дублікати — СТОП", city.slug, page)
                break

            if seen_checker:
                page_ids = [lst.id for lst in fresh_page]
                if seen_checker(page_ids):
                    log.info(
                        "Storia %s: сторінка %d — всі вже в БД — СТОП",
                        city.slug,
                        page,
                    )
                    break

            listings.extend(fresh_page)
            log.info(
                "Storia %s: сторінка %d — %d оголошень",
                city.slug,
                page,
                len(fresh_page),
            )

        return listings

    # ─────────────────────────────────────────────────────
    # HTML-парсинг
    # ─────────────────────────────────────────────────────

    def _parse_page(self, html: str, city_slug: str) -> list[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select('article[data-sentry-component="AdvertCard"]')

        out: list[Listing] = []
        for card in cards:
            lst = self._parse_card(card, city_slug)
            if lst is not None:
                out.append(lst)
        return out

    def _parse_card(self, card, city_slug: str) -> Listing | None:
        # ID + URL — з головного <a data-cy="listing-item-link">
        link_el = card.select_one('a[data-cy="listing-item-link"]')
        if not link_el:
            # fallback: будь-яке <a> з /ro/oferta/
            link_el = card.select_one('a[href*="/ro/oferta/"]')
        if not link_el:
            return None

        href = link_el.get("href", "")
        m = _ID_RE.search(href)
        if not m:
            return None

        listing_id = self.make_id(m.group(1))
        full_link = href if href.startswith("http") else f"{self.source.base_url}{href}"

        # Ціна
        price_el = card.select_one('[data-cy="listing-item-price"] span')
        price = price_el.get_text(strip=True) if price_el else ""

        # Заголовок
        title_el = card.select_one('[data-cy="listing-item-title"]')
        title = title_el.get_text(strip=True) if title_el else ""

        # Локація
        loc_el = card.select_one('[data-cy="advert-card-address"]')
        location = loc_el.get_text(strip=True) if loc_el else ""

        # Фото — перше
        img = card.select_one('img[data-cy="listing-item-image-source"]')
        photo = img.get("src", "") if img else ""

        # ── Характеристики з <dl>: dt підпис → dd значення
        rooms: str | None = None
        area_m2: float | None = None

        dl = card.find("dl")
        if dl:
            for dt in dl.find_all("dt"):
                label = dt.get_text(strip=True).lower()
                dd = dt.find_next_sibling("dd")
                if not dd:
                    continue
                value = dd.get_text(strip=True)

                if "camer" in label:  # "Numărul de camere"
                    rm = _ROOMS_RE.search(value)
                    if rm:
                        rooms = rm.group(1)
                elif "suprafaț" in label or "suprafata" in label:
                    # "Suprafață utilă" / "Suprafata utila" — реальна площа
                    am = _AREA_RE.search(value)
                    if am:
                        with contextlib.suppress(ValueError):
                            area_m2 = float(am.group(1).replace(",", "."))
                elif "metru pătrat" in label or "metru patrat" in label:
                    # "Prețul pe metru pătrat" — це ціна/м², НЕ площа. Ігноруємо.
                    pass

        # ── Fallback: якщо <dl> немає — витягуємо з тексту картки
        if rooms is None or area_m2 is None:
            text = card.get_text("\n", strip=True)
            if rooms is None:
                rm = _ROOMS_RE.search(text)
                if rm:
                    rooms = rm.group(1)
            if area_m2 is None:
                am = _AREA_RE.search(text)
                if am:
                    with contextlib.suppress(ValueError):
                        area_m2 = float(am.group(1).replace(",", "."))

        # ── Дата публікації
        created_at = self._extract_posted(card)

        return Listing(
            id=listing_id,
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price or "—",
            location=location,
            link=full_link,
            photo=photo,
            rooms=rooms,
            area_m2=area_m2,
            category="apartment",
            category_icon="🏢",
            category_label="Apartamente",
            created_at=created_at,
            raw={"source": SOURCE_KEY},
        )

    @staticmethod
    def _extract_posted(card) -> datetime | None:
        """Дата публікації.

        Логіка:
        1. NexusBadge з "Adăugat astăzi" → now
        2. NexusBadge з "Adăugat acum N zile/ore/minute" → now - N
        3. Будь-який елемент з "Reactualizat" → now (продавець оновив)
        4. Інакше → None (невідомо)

        На Storia ~75% карток без NexusBadge, але з "Reactualizat"
        деінде в тексті. Такі оголошення перепубліковані — вважаємо свіжими.
        """
        now = datetime.now(UTC)

        # ── 1-2. NexusBadge (пріоритет)
        badge = card.select_one('[data-nx-name="NexusBadge"] span')
        if badge:
            text = badge.get_text(strip=True)

            if _POSTED_TODAY_RE.search(text):
                return now

            m = _POSTED_AGO_RE.search(text)
            if m:
                n = int(m.group(1))
                unit = m.group(2).lower()
                delta = {
                    "zi": timedelta(days=n),
                    "zile": timedelta(days=n),
                    "ore": timedelta(hours=n),
                    "minute": timedelta(minutes=n),
                }.get(unit)
                return now - delta if delta else None

        # ── 3. Fallback: "Reactualizat" деінде в картці
        # Шукаємо в тексті всієї картки — елемент може бути в різних місцях
        card_text = card.get_text(" ", strip=True)
        if _REACTUALIZAT_RE.search(card_text):
            return now

        return None
