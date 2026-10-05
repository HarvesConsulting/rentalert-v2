"""PisosParser — HTML-парсер Pisos.com (Іспанія).

Обслуговує source 'pisos' (ES).
Один URL повертає всі типи житла — фільтруємо за заголовком.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import (
    human_delay,
    stealth_headers,
)

log = logging.getLogger(__name__)


# Ключові слова для фільтрації категорій за заголовком
_APARTMENT_WORDS = ("piso", "apartamento", "ático", "estudio", "dúplex")
_HOUSE_WORDS = ("casa", "chalet", "villa", "adosado", "pareado")
_ROOM_WORDS = ("habitación", "cuarto")


class PisosParser(Parser):
    """Парсер Pisos.com (ES)."""

    MAX_PAGES = 10  # запобіжник від зациклення

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення для міста й категорій (з пагінацією)."""
        city_slug = self.external_id(city)
        if city_slug is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        try:
            all_listings = self._fetch_all_pages(
                city_slug=str(city_slug),
                city=city,
                seen_checker=seen_checker,
            )
        except Exception as e:
            log.exception("Pisos %s failed: %s", city_slug, e)
            return []

        wanted = set(self.filter_categories(categories))
        if not wanted:
            return []

        result: list[Listing] = []
        for lst in all_listings:
            if lst.category in wanted:
                result.append(lst)

        log.info("Pisos %s: %d оголошень (відфільтровано)", city_slug, len(result))
        return result

    # ─────────────────────────────────────────────────────
    # Внутрішнє
    # ─────────────────────────────────────────────────────

    def _fetch_all_pages(
        self,
        *,
        city_slug: str,
        city: City,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує всі сторінки, поки не догнали оновлення."""
        all_listings: list[Listing] = []
        seen_in_run: set[str] = set()
        empty_pages_streak = 0

        for page in range(1, self.MAX_PAGES + 1):
            url = self._make_page_url(city_slug, page)

            human_delay()

            try:
                response = cffi_requests.get(
                    url,
                    impersonate="chrome",
                    headers=stealth_headers(),
                    timeout=30,
                )
            except Exception as e:
                log.warning("Pisos GET failed (page %d): %s", page, e)
                break

            if response.status_code != 200:
                log.warning(
                    "Pisos %s page %d → HTTP %d",
                    city_slug,
                    page,
                    response.status_code,
                )
                break

            soup = BeautifulSoup(response.text, "html.parser")
            # Картки мають клас ad-preview
            cards = soup.find_all("div", class_="ad-preview")

            if not cards:
                log.info("Pisos %s: сторінка %d порожня — СТОП", city_slug, page)
                break

            page_listings: list[Listing] = []
            for card in cards:
                try:
                    lst = self._parse_card(card=card, city_slug=city.slug)
                    if lst is not None and lst.id not in seen_in_run:
                        seen_in_run.add(lst.id)
                        page_listings.append(lst)
                except Exception as e:
                    log.exception("Помилка парсингу card: %s", e)

            if not page_listings:
                empty_pages_streak += 1
                log.info(
                    "Pisos %s: сторінка %d — всі дублікати (%d підряд)",
                    city_slug,
                    page,
                    empty_pages_streak,
                )
                if empty_pages_streak >= 3:
                    log.info("Pisos %s: 3 порожні сторінки підряд — СТОП", city_slug)
                    break
                continue

            if seen_checker:
                page_ids = [lst.id for lst in page_listings]
                if seen_checker(page_ids):
                    empty_pages_streak += 1
                    log.info(
                        "Pisos %s: сторінка %d — всі вже в БД (%d підряд)",
                        city_slug,
                        page,
                        empty_pages_streak,
                    )
                    if empty_pages_streak >= 3:
                        log.info("Pisos %s: 3 сторінки без нових — СТОП", city_slug)
                        break
                    continue

            empty_pages_streak = 0
            all_listings.extend(page_listings)
            log.info(
                "Pisos %s: сторінка %d — %d оголошень",
                city_slug,
                page,
                len(page_listings),
            )

        return all_listings

    @staticmethod
    def _make_page_url(city_slug: str, page: int) -> str:
        """Формує URL сторінки.

        URL: /alquiler/pisos-{slug}/{page}/
        """
        base = "https://www.pisos.com"
        url = f"{base}/alquiler/pisos-{city_slug}/"
        if page > 1:
            url += f"{page}/"
        return url

    def _parse_card(
        self,
        *,
        card: Any,
        city_slug: str,
    ) -> Listing | None:
        """Парсить одну картку оголошення."""
        ad_id = card.get("id")
        if not ad_id:
            return None

        href = card.get("data-lnk-href") or ""
        url_full = f"https://www.pisos.com{href}" if href.startswith("/") else href

        # Заголовок
        title_el = card.select_one(".ad-preview__title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # Категорія за заголовком
        category_key, icon, label = self._detect_category(title)
        if category_key is None:
            return None

        # Ціна
        price_el = card.select_one(".ad-preview__price")
        price = price_el.get_text(strip=True) if price_el else ""

        # Локація
        location_el = card.select_one(".ad-preview__subtitle")
        location = location_el.get_text(strip=True) if location_el else ""

        # Характеристики: кімнати, ванні, площа
        chars = card.select(".ad-preview__char")
        rooms: str | None = None
        for ch in chars:
            text = ch.get_text(strip=True)
            if "hab" in text.lower():
                m = re.search(r"(\d+)", text)
                if m:
                    rooms = m.group(1)
                break

        # Фото
        photo = self._extract_photo(card)

        # Опис (може бути відсутній)
        desc_el = card.select_one(".ad-preview__description")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Додаємо опис до raw (він може бути довгий, обрізаємо)
        raw: dict[str, Any] = {
            "description": description[:500] if description else "",
        }

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
            raw=raw,
        )


@staticmethod
def _extract_photo(card: Any) -> str:
    """Витягує URL фото з картки Pisos.com.

    Підтримує:
      - звичайний src
      - lazy-loading через data-src, data-original, data-lazy-src
      - srcset
      - fallback на будь-який img з fotos.imghs.net / imghs.net
      - ігнорує placeholder-и (data:image/...)
    """
    # 1. Основний селектор (картка з каруселлю)
    main_img = card.select_one(".carousel__main-photo img, .carousel__main-photo--mosaic img")

    # 2. Усі img у картці (порядок: основний перший, потім решта)
    candidates: list[Any] = []
    if main_img:
        candidates.append(main_img)
    candidates.extend(card.find_all("img"))

    for candidate in candidates:
        if not candidate:
            continue

        # Пробуємо різні атрибути для URL
        src = (
            candidate.get("src")
            or candidate.get("data-src")
            or candidate.get("data-original")
            or candidate.get("data-lazy-src")
            or ""
        )

        # Якщо src порожній або placeholder — пробуємо srcset
        if not src or src.startswith("data:"):
            srcset = candidate.get("srcset", "") or ""
            if srcset:
                # srcset = "url1 1x, url2 2x" — беремо перший URL
                src = srcset.split(",")[0].strip().split(" ")[0]

        if not src or src.startswith("data:"):
            continue

        # Реальне фото оголошення (Pisos використовує fotos.imghs.net)
        if "fotos.imghs.net" in src or "imghs.net" in src:
            return src

    return ""

    # ─────────────────────────────────────────────────────
    # Витягування категорії
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _detect_category(title: str) -> tuple[str | None, str, str]:
        """Визначає категорію за заголовком."""
        t = title.lower()

        if any(w in t for w in _APARTMENT_WORDS):
            return "apartment", "🏢", "Piso"
        if any(w in t for w in _HOUSE_WORDS):
            return "house", "🏠", "Casa"
        if any(w in t for w in _ROOM_WORDS):
            return "room", "🚪", "Habitación"

        return None, "🏠", "Alquiler"
