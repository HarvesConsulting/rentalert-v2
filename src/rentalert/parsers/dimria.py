"""DimriaParser — парсер DIM.RIA через офіційний API.

Вимагає DIMRIA_API_KEY у env. Має rate limit (3 сек між запитами).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser

log = logging.getLogger(__name__)

DIMRIA_BASE = "https://developers.ria.com/dom"
DIMRIA_MIN_INTERVAL = 3.0  # секунд між запитами
DIMRIA_RECENT_DAYS = 3     # днів — вікно свіжості для DIM.RIA
DIMRIA_MAX_ITEMS = 15      # обмеження item за один цикл

# ─── Rate limit (спільний для всіх екземплярів) ───
_last_request_time = 0.0
_rate_lock = threading.Lock()


def _wait_for_slot() -> None:
    """Блокує потік, поки не пройде DIMRIA_MIN_INTERVAL з моменту останнього запиту."""
    global _last_request_time
    while True:
        with _rate_lock:
            now = time.time()
            elapsed = now - _last_request_time
            if elapsed >= DIMRIA_MIN_INTERVAL:
                _last_request_time = now
                return
            wait = DIMRIA_MIN_INTERVAL - elapsed
        time.sleep(wait + 0.2)


class DimriaParser(Parser):
    """Парсер DIM.RIA.

    Використовує API developers.ria.com з ключем DIMRIA_API_KEY.
    """

    def __init__(self, source) -> None:
        super().__init__(source)
        self.api_key = os.environ.get("DIMRIA_API_KEY", "")

    def fetch(self, city: City, categories: list[str]) -> list[Listing]:
        """Завантажує оголошення DIM.RIA для міста."""
        if not self.api_key:
            log.warning("DIMRIA_API_KEY не встановлено — пропускаю DIM.RIA")
            return []

        city_id = self.external_id(city)
        if city_id is None:
            log.warning("City %r не має refs для %r", city.slug, self.source.key)
            return []

        # 1. Отримати список ID
        try:
            ids = self._search(city_id)
        except Exception as e:
            log.exception("DIM.RIA search failed: %s", e)
            return []

        if not ids:
            return []

        # 2. Для кожного ID — деталі
        listings: list[Listing] = []
        for realty_id in ids[:DIMRIA_MAX_ITEMS]:
            try:
                lst = self._fetch_info(realty_id, city)
            except Exception as e:
                log.exception("DIM.RIA info %s failed: %s", realty_id, e)
                continue

            if lst is not None:
                listings.append(lst)

        return listings

    # ─────────────────────────────────────────────────────
    # API
    # ─────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET до DIM.RIA з rate limit."""
        _wait_for_slot()
        full_params = {"api_key": self.api_key}
        if params:
            full_params.update(params)

        try:
            response = cffi_requests.get(
                f"{DIMRIA_BASE}/{path}",
                params=full_params,
                timeout=25,
            )
        except Exception as e:
            log.warning("DIM.RIA GET /%s: %s", path, e)
            return None

        if response.status_code != 200:
            log.warning("DIM.RIA /%s → HTTP %d", path, response.status_code)
            return None

        try:
            return response.json()
        except Exception as e:
            log.warning("DIM.RIA /%s → invalid JSON: %s", path, e)
            return None

    def _search(self, city_id: int | str) -> list[int]:
        """Пошук ID оголошень."""
        data = self._get(
            "search",
            {
                "category": 1,
                "realty_type": 2,
                "operation_type": 2,
                "city_id": city_id,
                "limit": 20,
                "price_from": 70,
                "price_to": 600,
            },
        )
        if not isinstance(data, dict):
            return []
        items = data.get("items", []) or []
        return [int(i) for i in items if i]

    def _fetch_info(self, realty_id: int, city: City) -> Listing | None:
        """Завантажує деталі оголошення."""
        data = self._get(f"info/{realty_id}")
        if not isinstance(data, dict) or not data:
            return None

        price_str = self._extract_price(data)
        location = self._extract_location(data)
        photo = self._extract_photo(data)
        rooms = str(data.get("rooms_count") or "") or None
        created_at = self._extract_created_at(data)

        title = (data.get("title") or "")[:200] or "Оголошення DIM.RIA"

        return Listing(
            id=self.make_id(realty_id),
            source_key=self.source.key,
            city_slug=city.slug,
            title=title,
            price=price_str,
            location=location,
            link=f"https://dom.ria.com/uk/realty-{realty_id}.html",
            photo=photo,
            rooms=rooms,
            category="apartment",
            category_icon="🏘",
            category_label="DIM.RIA",
            created_at=created_at,
            raw=data,
        )

    # ─────────────────────────────────────────────────────
    # Витягування полів
    # ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_price(data: dict[str, Any]) -> str:
        price = data.get("price") or {}
        if isinstance(price, dict):
            value = price.get("total") or price.get("price")
        else:
            value = price
        return f"{value} $" if value else "—"

    @staticmethod
    def _extract_location(data: dict[str, Any]) -> str:
        parts = [
            (data.get("city_name") or "").strip(),
            (data.get("district_name") or "").strip(),
            (data.get("street_name") or "").strip(),
        ]
        parts = [p for p in parts if p]
        return ", ".join(parts) if parts else "DIM.RIA"

    @staticmethod
    def _extract_photo(data: dict[str, Any]) -> str:
        photos = data.get("photos") or data.get("images") or []
        if not photos or not isinstance(photos, list):
            return ""
        first = photos[0]
        if isinstance(first, dict):
            url = (
                first.get("file")
                or first.get("url")
                or first.get("link")
                or first.get("big")
                or ""
            )
        elif isinstance(first, str):
            url = first
        else:
            return ""
        if url and not url.startswith("http"):
            url = f"https://dom.ria.com{url}" if url.startswith("/") else f"https://{url}"
        return url

    @staticmethod
    def _extract_created_at(data: dict[str, Any]) -> datetime | None:
        raw = data.get("date_published") or data.get("publishing_date") or ""
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            # Перевірка свіжості
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now(UTC)
            if (now - dt) < timedelta(days=DIMRIA_RECENT_DAYS):
                return dt
            return None
        except Exception:
            return None
