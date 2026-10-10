"""MerrjepParser — парсер MerrJep.al (Албанія) через JSON-LD.

Обслуговує source 'merrjep'.

Особливість: сайт рендерить картки через JS, але в HTML є
<script type="application/ld+json"> з усіма оголошеннями (schema.org).
Тому BeautifulSoup + json.loads — достатньо.

seen_checker: callback (list[str]) -> bool. Приймає список ID і
повертає True, якщо ВСІ вони вже в БД. Використовується для ранньої
зупинки парсингу, щоб не робити зайвих запитів.
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
from rentalert.parsers.stealth import human_delay, stealth_headers

log = logging.getLogger(__name__)


# Категорії на сайті (slug у URL)
_CATEGORY_SLUGS: dict[str, str] = {
    "apartment": "apartamente",
    "house": "shtepi",
}

# Символи валют
_CURRENCY_SYMBOLS: dict[str, str] = {
    "EUR": "€",
    "LEK": "L",
    "ALL": "L",
    "USD": "$",
}


class MerrjepParser(Parser):
    """Парсер MerrJep.al через JSON-LD (schema.org)."""

    BASE_URL = "https://www.merrjep.al"
    MAX_PAGES = 3  # зменшено з 5, щоб менше 503

    # Якщо 3 сторінки підряд усі в БД — зупиняємось
    EMPTY_STREAK_LIMIT = 3

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        wanted = set(self.filter_categories(categories))
        if not wanted:
            return []

        all_listings: list[Listing] = []
        seen_ids: set[str] = set()

        for cat_key, cat_slug in _CATEGORY_SLUGS.items():
            if cat_key not in wanted:
                continue

            empty_streak = 0

            for page in range(1, self.MAX_PAGES + 1):
                human_delay(min_sec=2.0, max_sec=4.0)

                url = self._make_url(str(city_slug), cat_slug, page)
                items = self._fetch_page(url, str(city_slug), page)

                if not items:
                    log.info(
                        "MerrJep %s/%s: стор. %d — порожня, СТОП",
                        city_slug,
                        cat_key,
                        page,
                    )
                    break

                page_listings: list[Listing] = []
                for raw in items:
                    try:
                        lst = self._parse_one(raw, city.slug)
                    except Exception as e:
                        log.exception("MerrJep parse_one: %s", e)
                        continue

                    if lst is None or lst.id in seen_ids:
                        continue
                    seen_ids.add(lst.id)

                    if lst.category in wanted:
                        page_listings.append(lst)

                log.info(
                    "MerrJep %s/%s: стор. %d — %d оголошень",
                    city_slug,
                    cat_key,
                    page,
                    len(page_listings),
                )

                # ── Перевірка seen_checker ──
                # Якщо всі оголошення на сторінці вже в БД — рахуємо streak
                if seen_checker and page_listings:
                    page_ids = [lst.id for lst in page_listings]
                    if seen_checker(page_ids):
                        empty_streak += 1
                        log.info(
                            "MerrJep %s/%s: стор. %d — всі вже в БД (%d підряд)",
                            city_slug,
                            cat_key,
                            page,
                            empty_streak,
                        )
                        if empty_streak >= self.EMPTY_STREAK_LIMIT:
                            log.info(
                                "MerrJep %s/%s: %d сторінок без нових — СТОП",
                                city_slug,
                                cat_key,
                                self.EMPTY_STREAK_LIMIT,
                            )
                            break
                        continue

                # Якщо на сторінці нічого нового (в межах fetch) — СТОП
                if not page_listings:
                    empty_streak += 1
                    if empty_streak >= self.EMPTY_STREAK_LIMIT:
                        log.info(
                            "MerrJep %s/%s: %d порожніх сторінок підряд — СТОП",
                            city_slug,
                            cat_key,
                            self.EMPTY_STREAK_LIMIT,
                        )
                        break
                    continue

                empty_streak = 0
                all_listings.extend(page_listings)

        log.info(
            "MerrJep %s: %d оголошень (усі категорії)",
            city_slug,
            len(all_listings),
        )
        return all_listings

    def _make_url(self, city_slug: str, category_slug: str, page: int) -> str:
        url = f"{self.BASE_URL}/njoftime/imobiliare-vendbanime/{category_slug}/me-qera/{city_slug}"
        if page > 1:
            url += f"?page={page}"
        return url

    def _fetch_page(
        self,
        url: str,
        city_slug: str,
        page: int,
    ) -> list[dict[str, Any]]:
        """Завантажує сторінку і витягує ItemList з JSON-LD."""
        try:
            resp = cffi_requests.get(
                url,
                impersonate="chrome",
                headers=stealth_headers(),
                timeout=30,
            )
        except Exception as e:
            log.warning("MerrJep GET %s failed: %s", url, e)
            return []

        if resp.status_code != 200:
            log.warning("MerrJep %s → HTTP %d", url, resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (ValueError, TypeError):
                continue

            for node in data.get("@graph", []):
                if node.get("@type") == "ItemList":
                    return [
                        el["item"]
                        for el in node.get("itemListElement", [])
                        if isinstance(el, dict) and "item" in el
                    ]

        return []

    def _parse_one(
        self,
        raw: dict[str, Any],
        city_slug: str,
    ) -> Listing | None:
        url = raw.get("url") or ""
        if not url:
            return None

        # ID — останнє число в URL: /njoftim/.../19980438
        m = re.search(r"/(\d+)/?$", url)
        if not m:
            return None
        external_id = m.group(1)

        name = (raw.get("name") or "").strip()
        if not name:
            return None

        # Ціна
        offers = raw.get("offers") or {}
        price_val = offers.get("price")
        currency = offers.get("priceCurrency") or "EUR"
        symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency)
        if price_val is not None:
            try:
                price = f"{int(float(price_val))} {symbol}"
            except (TypeError, ValueError):
                price = "—"
        else:
            price = "—"

        # Фото
        images = raw.get("image") or []
        photo = images[0] if images else ""

        # Категорія з name
        category_key, icon, label = self._detect_category(name)

        # Кімнати з name (наприклад "2+1" → 3, "3-dhome" → 3)
        rooms = self._extract_rooms(name)

        # Локація з name (остання частина після коми)
        location = self._extract_location(name, city_slug)

        # Title — додаємо ціну
        title = name
        if price != "—":
            title = f"{name} — {price}"

        return Listing(
            id=self.make_id(external_id),
            source_key=self.source.key,
            city_slug=city_slug,
            title=title,
            price=price,
            location=location,
            link=url,
            photo=photo,
            rooms=rooms,
            category=category_key,
            category_icon=icon,
            category_label=label,
            created_at=None,
            area_m2=None,
            raw=raw,
        )

    @staticmethod
    def _detect_category(name: str) -> tuple[str, str, str]:
        n = name.lower()
        if any(w in n for w in ("apartament", "duplex", "garsonier", "studio", "banes")):
            return "apartment", "🏢", "Apartament"
        if any(w in n for w in ("shtepi", "vilë", "vile", "katesh")):
            return "house", "🏠", "Shtëpi"
        if "dhome" in n or "dhomë" in n:
            return "room", "🚪", "Dhomë"
        return "apartment", "🏢", "Apartament"

    @staticmethod
    def _extract_rooms(name: str) -> str | None:
        """Витягує кількість кімнат з назви.

        'Apartament 2+1' → 3
        '3-dhome' → 3
        """
        m = re.search(r"(\d+)\s*\+\s*(\d+)", name)
        if m:
            return str(int(m.group(1)) + int(m.group(2)))

        m = re.search(r"(\d+)\s*[- ]?\s*dhom", name, re.IGNORECASE)
        if m:
            return m.group(1)

        return None

    @staticmethod
    def _extract_location(name: str, city_slug: str) -> str:
        """Локація — остання частина після коми + місто."""
        cleaned = name.replace('"', "").replace("'", "").strip()

        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        if len(parts) >= 2:
            return f"{parts[-1]}, {city_slug}"
        return city_slug
