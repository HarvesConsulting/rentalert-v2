"""Parser999Md — парсер 999.md через GraphQL API.

999.md — найбільша дошка оголошень Молдови.

Ендпоінт: https://999.md/graphql (публічний, без авторизації).
Мова: через заголовок `lang: ru` або `lang: ro`.

Стратегія парсингу:
  Бот відслідковує НОВІ оголошення — ті, яких ще немає в БД.
  999.md сортує результати за датою (найновіші — першими).
  Тому MAX_PAGES=2 достатньо: 60 найновіших оголошень
  покривають усе, що з'явилось з минулого циклу.
  seen_checker зупиняє парсер, як тільки вся сторінка
  вже відома — типово це відбувається на 1-й сторінці.

Категорії:
  categoryId=270 — Нерухомість
  subCategoryId=1404 — Квартири
  subCategoryId=1406 — Будинки

Фільтри (featureId, для searchAds):
  1 — тип пропозиції (912 = оренда)
  8 — локація (city). refs.999md у data/cities/md.json — це ID міст.

Feature IDs (для advert.feature(id:)):
  1 — тип пропозиції
  2 — ціна
  3 — координати (lat, lon)
  7 — регіон
  8 — місто
  9 — сектор
  10 — вулиця
  13 — опис
  14 — фото
  16 — контакти

Особливості API:
  - advert(input: {id: ...}) очікує ID як РЯДОК, не число.
  - Поля url/slug у схемі Advert НЕМАЄ — посилання через /ru/{id}.
  - Поле posted існує, але завжди порожнє ("").
    Тому created_at завжди None. Це не проблема: бот
    відслідковує нові через seen_checker, а не через дату.
  - i.999.md має невалідний SSL — використовуємо справжній
    CDN i.simpalsmedia.com для фото.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser
from rentalert.parsers.stealth import (
    fetch_with_retry,
    stealth_headers,
)

log = logging.getLogger(__name__)

MD999_GRAPHQL = "https://999.md/graphql"
MD999_IMPERSONATE = "chrome"

# Категорії
CATEGORY_REAL_ESTATE = 270
SUBCATEGORY_APARTMENTS = 1404
SUBCATEGORY_HOUSES = 1406

# Фільтри (featureId у searchAds)
FILTER_OFFER_TYPE = 1
FILTER_LOCATION = 8  # feature 8 = city

# Значення опцій
OPTION_RENT = 912  # оренда

# Feature IDs (для advert.feature(id:))
FEATURE_PRICE = 2
FEATURE_REGION = 7
FEATURE_CITY = 8
FEATURE_SECTOR = 9
FEATURE_STREET = 10
FEATURE_DESCRIPTION = 13
FEATURE_IMAGES = 14
FEATURE_MAP_POINT = 3

# Пагінація
# ⚠️ MAX_PAGES = 2: 999.md сортує за датою (найновіші — першими).
# 60 оголошень достатньо для покриття всього, що з'явилось
# з минулого циклу. seen_checker зупинить парсер раніше, якщо
# вся сторінка вже в БД.
PAGE_SIZE = 30
MAX_PAGES = 2
REQUEST_DELAY = 0.15

# Мапінг категорій нашого бота → subCategoryId 999.md
CATEGORY_MAP = {
    "apartment": SUBCATEGORY_APARTMENTS,
    "house": SUBCATEGORY_HOUSES,
}


class Parser999Md(Parser):
    """Парсер 999.md через GraphQL API."""

    def __init__(self, source) -> None:
        super().__init__(source)
        self._session: cffi_requests.Session = cffi_requests.Session(
            impersonate=MD999_IMPERSONATE,
        )

    # ─────────────────────────────────────────────────────
    # Публічний API
    # ─────────────────────────────────────────────────────

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Повертає оголошення 999.md для міста й категорій."""
        location_id = self.external_id(city)
        if location_id is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        supported = self.filter_categories(categories)
        if not supported:
            return []

        all_listings: list[Listing] = []
        seen_ids: set[str] = set()

        for cat in supported:
            subcategory_id = CATEGORY_MAP.get(cat)
            if subcategory_id is None:
                continue

            try:
                batch = self._fetch_category(
                    subcategory_id=subcategory_id,
                    location_id=location_id,
                    city=city,
                    category=cat,
                    seen_checker=seen_checker,
                )
            except Exception as e:
                log.exception("999.md %s/%s failed: %s", city.slug, cat, e)
                continue

            for lst in batch:
                if lst.id not in seen_ids:
                    seen_ids.add(lst.id)
                    all_listings.append(lst)

        log.info("999.md %s: %d оголошень", city.slug, len(all_listings))
        return all_listings

    # ─────────────────────────────────────────────────────
    # Категорія
    # ─────────────────────────────────────────────────────

    def _fetch_category(
        self,
        *,
        subcategory_id: int,
        location_id: Any,
        city: City,
        category: str,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        """Завантажує оголошення однієї категорії.

        Пагінація з зупинкою:
          - коли прийшла порожня сторінка,
          - коли прийшло менше PAGE_SIZE,
          - коли вся поточна сторінка вже в БД (seen_checker == True).
        """
        listings: list[Listing] = []
        seen_in_run: set[str] = set()
        skip = 0

        for _page in range(MAX_PAGES):
            data = self._gql_search(
                subcategory_id=subcategory_id,
                location_id=location_id,
                skip=skip,
                limit=PAGE_SIZE,
            )

            if data is None:
                break

            ads = data.get("ads", []) or []
            if not ads:
                break

            page_listings: list[Listing] = []
            for ad in ads:
                try:
                    listing = self._fetch_advert(ad, city, category)
                    if listing is not None and listing.id not in seen_in_run:
                        seen_in_run.add(listing.id)
                        page_listings.append(listing)
                except Exception as e:
                    log.exception("999.md advert %s failed: %s", ad.get("id"), e)

            # Контракт seen_checker (з base.py):
            #   True = УСІ передані ID вже є в БД.
            if seen_checker is not None and page_listings:
                page_ids = [lst.id for lst in page_listings]
                if seen_checker(page_ids):
                    log.info(
                        "999.md %s/%s: вся сторінка (%d) вже відома, стоп",
                        city.slug,
                        category,
                        len(page_ids),
                    )
                    break

            listings.extend(page_listings)

            if len(ads) < PAGE_SIZE:
                break

            skip += PAGE_SIZE
            time.sleep(REQUEST_DELAY)

        return listings

    # ─────────────────────────────────────────────────────
    # GraphQL
    # ─────────────────────────────────────────────────────

    def _gql_search(
        self,
        *,
        subcategory_id: int,
        location_id: Any,
        skip: int,
        limit: int,
    ) -> dict | None:
        """searchAds-запит з фільтрами."""
        try:
            location_int = int(location_id)
        except (TypeError, ValueError):
            log.warning(
                "999.md: невалідний location_id=%r для %s",
                location_id,
                subcategory_id,
            )
            return None

        query = """
        query SearchAds($input: Ads_SearchInput!) {
          searchAds(input: $input) {
            count
            ads {
              id
              title
              posted
            }
          }
        }
        """
        variables = {
            "input": {
                "categoryId": CATEGORY_REAL_ESTATE,
                "subCategoryId": subcategory_id,
                "filters": [
                    {
                        "filterId": FILTER_OFFER_TYPE,
                        "features": [
                            {
                                "featureId": FILTER_OFFER_TYPE,
                                "optionIds": [OPTION_RENT],
                            },
                        ],
                    },
                    {
                        "filterId": FILTER_LOCATION,
                        "features": [
                            {
                                "featureId": FILTER_LOCATION,
                                "optionIds": [location_int],
                            },
                        ],
                    },
                ],
                "pagination": {"skip": skip, "limit": limit},
            }
        }
        response = self._post(query, variables)
        if response is None:
            return None

        result = response.get("data", {}).get("searchAds")
        if isinstance(result, dict):
            log.debug(
                "999.md searchAds count=%s skip=%s",
                result.get("count"),
                skip,
            )
            return result
        return None

    def _fetch_advert(self, ad: dict, city: City, category: str) -> Listing | None:
        """Завантажує деталі оголошення через advert(id).

        ⚠️ advert(input: {id: ...}) очікує ID як РЯДОК.
        """
        query = """
        query GetAdvert($input: AdvertInput!) {
          advert(input: $input) {
            id
            title
            posted
            state
            owner { login }
            price: feature(id: 2) { value }
            description: feature(id: 13) { value }
            photos: feature(id: 14) { value }
            region: feature(id: 7) { value }
            city: feature(id: 8) { value }
            sector: feature(id: 9) { value }
            street: feature(id: 10) { value }
          }
        }
        """
        response = self._post(query, {"input": {"id": str(ad["id"])}})
        if response is None:
            return None

        advert = response.get("data", {}).get("advert")
        if advert is None:
            return None

        return self._parse_advert(advert, city, category)

    def _post(self, query: str, variables: dict) -> dict | None:
        """POST-запит до 999.md GraphQL з retry."""

        def _do_post(url: str, **kwargs) -> Any:
            return self._session.post(url, **kwargs)

        # stealth_headers + Content-Type для JSON
        headers = stealth_headers(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "lang": "ru",
                "Origin": "https://999.md",
                "Referer": "https://999.md/",
            }
        )

        response = fetch_with_retry(
            _do_post,
            MD999_GRAPHQL,
            retries=2,
            backoff_sec=3,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30,
        )

        if response is None:
            log.warning("999.md: усі спроби вичерпано")
            return None

        if response.status_code != 200:
            log.warning("999.md HTTP %d", response.status_code)
            return None

        try:
            data = response.json()
        except Exception as e:
            log.warning("999.md JSON decode error: %s", e)
            return None

        if "errors" in data:
            log.warning("999.md GraphQL errors: %s", data["errors"])
            return None

        return dict(data)

    # ─────────────────────────────────────────────────────
    # Мапінг
    # ─────────────────────────────────────────────────────

    def _parse_advert(self, advert: dict, city: City, category: str) -> Listing | None:
        """Мапить Advert (з alias) → Listing."""
        advert_id = advert.get("id")
        if not advert_id:
            return None

        title = advert.get("title") or "999.md"

        # ── Ціна ──
        price_str = self._format_price((advert.get("price") or {}).get("value") or {})

        # ── Локація ──
        street = (advert.get("street") or {}).get("value") or ""
        city_data = (advert.get("city") or {}).get("value") or {}
        sector_data = (advert.get("sector") or {}).get("value") or {}
        region_data = (advert.get("region") or {}).get("value") or {}

        location_parts: list[str] = []
        if street:
            location_parts.append(str(street))
        if isinstance(sector_data, dict) and sector_data.get("translated"):
            location_parts.append(sector_data["translated"])
        if isinstance(city_data, dict) and city_data.get("translated"):
            location_parts.append(city_data["translated"])
        if isinstance(region_data, dict) and region_data.get("translated"):
            location_parts.append(region_data["translated"])
        location = ", ".join(location_parts) or city.name

        # ── Фото ──
        photo = self._first_photo((advert.get("photos") or {}).get("value"))

        # ── Категорія ──
        icon, label = self._category_meta(category)

        # ── URL (fallback: поля url у схемі немає) ──
        link = f"https://999.md/ru/{advert_id}"

        # ── Rooms з title ──
        rooms = self._extract_rooms(title)

        # ── Площа з title ──
        area_m2 = self._extract_area(title)

        # ── created_at ──
        # 999.md не повертає дату публікації (posted="").
        # Це не проблема: бот відслідковує нові через seen_checker.
        created_at = None

        return Listing(
            id=self.make_id(advert_id),
            source_key=self.source.key,
            city_slug=city.slug,
            title=title[:200],
            price=price_str,
            location=location,
            link=link,
            photo=photo,
            rooms=rooms,
            area_m2=area_m2,
            category=category,
            category_icon=icon,
            category_label=label,
            created_at=created_at,
            raw=advert,
        )

    # ─────────────────────────────────────────────────────
    # Хелпери
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_rooms(title: str) -> str | None:
        """Витягує кількість кімнат з title (RU/RO/UA/EN)."""
        if not title:
            return None
        patterns = [
            r"(\d+)\s*-\s*комнатная",
            r"(\d+)\s*-\s*комн",
            r"(\d+)\s*camere",
            r"(\d+)\s*кімнат",
            r"(\d+)\s*room",
            r"(\d+)\s*[Кк]\.",
        ]
        for p in patterns:
            m = re.search(p, title, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _extract_area(title: str) -> float | None:
        """Витягує площу з title: '28 м²', '75 кв.м', '50 m2'.

        Повертає float (28.5) або None, якщо не вдалось.
        """
        if not title:
            return None
        # Формати: "28 м²", "28м²", "28 m²", "28 m2", "28 кв.м", "28 кв м"
        pattern = r"(\d+(?:[.,]\d+)?)\s*(?:м²|m²|m2|кв\.?\s*м)"
        m = re.search(pattern, title, re.IGNORECASE)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _first_photo(photos_data: Any) -> str:
        """Повертає URL першого фото (list | dict | str).

        API 999.md повертає у feature(id: 14) лише filename,
        але справжній CDN — i.simpalsmedia.com (не i.999.md!).
        i.999.md має невалідний SSL (NET::ERR_CERT_COMMON_NAME_INVALID),
        і Telegram не може його завантажити.

        Формат:
            https://i.simpalsmedia.com/999.md/BoardImages/{SIZE}//{FILENAME}
        """
        if not photos_data:
            return ""
        if isinstance(photos_data, dict):
            photos_data = list(photos_data.values())
        if not isinstance(photos_data, list) or not photos_data:
            return ""
        first = photos_data[0]
        if not isinstance(first, str) or not first:
            return ""
        # Якщо API вже повернув повний URL — використовуємо як є
        if first.startswith("http"):
            return first
        # Інакше — будуємо URL на справжньому CDN
        return f"https://i.simpalsmedia.com/999.md/BoardImages/900x900//{first}"

    @staticmethod
    def _format_price(price_data: dict) -> str:
        """Форматує ціну: '450 €', '1 200 MDL'."""
        if not isinstance(price_data, dict):
            return "—"
        value = price_data.get("value")
        unit = price_data.get("unit", "")
        down = price_data.get("down_payment")

        if value is None or value == "":
            return "—"

        try:
            value_num = float(str(value).replace(",", ".").replace(" ", ""))
            value_str = f"{value_num:g}"
        except (ValueError, TypeError):
            value_str = str(value)

        currency_map = {
            "UNIT_EUR": "€",
            "UNIT_MDL": "MDL",
            "UNIT_USD": "$",
            "EUR": "€",
            "MDL": "MDL",
            "USD": "$",
        }
        currency = currency_map.get(unit, unit or "")

        result = f"{value_str} {currency}".strip()
        if down:
            result += f" + {down} {currency}".strip()
        return result

    @staticmethod
    def _category_meta(category: str) -> tuple[str, str]:
        icons = {"apartment": "🏢", "house": "🏠"}
        labels = {"apartment": "Квартиры", "house": "Дома"}
        return icons.get(category, "🏠"), labels.get(category, category)
