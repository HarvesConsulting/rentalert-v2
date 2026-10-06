"""BezrealitkyParser — парсер Bezrealitky.cz через GraphQL API."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from curl_cffi import requests as cffi_requests

from rentalert.catalog.models import City
from rentalert.parsers.base import Listing, Parser

log = logging.getLogger(__name__)

BEZREALITKY_GRAPHQL = "https://api.bezrealitky.cz/graphql/"

PAGE_SIZE = 100
MAX_PAGES = 20
REQUEST_DELAY = 0.5

DISPOSITION_MAP = {
    "GARSONIERA": "Garsoniéra",
    "DISP_1_KK": "1+kk",
    "DISP_2_KK": "2+kk",
    "DISP_3_KK": "3+kk",
    "DISP_4_KK": "4+kk",
    "DISP_5_KK": "5+kk",
    "DISP_1_1": "1+1",
    "DISP_2_1": "2+1",
    "DISP_3_1": "3+1",
    "DISP_4_1": "4+1",
    "DISP_5_1": "5+1",
    "DISP_2_2": "2+2",
    "DISP_3_2": "3+2",
    "DISP_4_2": "4+2",
    "DISP_5_2": "5+2",
    "DISP_ATYPICKY": "Atypický",
    "DISP_POKOJ": "Pokoj",
    "OSTATNI": "Ostatní",
    "UNDEFINED": None,
}

GQL_QUERY = """
query ListAdverts(
  $regionOsmIds: [ID!],
  $offerType: [OfferType!],
  $estateType: [EstateType!],
  $limit: Int,
  $offset: Int,
  $order: ResultOrder
) {
  listAdverts(
    regionOsmIds: $regionOsmIds,
    offerType: $offerType,
    estateType: $estateType,
    limit: $limit,
    offset: $offset,
    order: $order
  ) {
    totalCount
    list {
      id
      uri
      price
      originalPrice
      charges
      serviceCharges
      utilityCharges
      deposit
      currency
      surface
      disposition
      estateType
      offerType
      address(locale: CS)
      street
      city(locale: CS)
      cityDistrict(locale: CS)
      zip
      gps { lat lng }
      etage
      totalFloors
      mainImage { url(filter: RECORD_MAIN) }
      publicImages(limit: 5) { url(filter: RECORD_MAIN) }
      tags(locale: CS)
      isNew
      isDiscounted
      reserved
      petFriendly
      roommate
      shortTerm
      lift
      garage
      parking
      barrierFree
    }
  }
}
"""


class BezrealitkyParser(Parser):
    """Парсер Bezrealitky.cz через GraphQL API."""

    def __init__(self, source: Any) -> None:
        super().__init__(source)
        self._session: Any = cffi_requests.Session(impersonate="chrome120")

    def fetch(
        self,
        city: City,
        categories: list[str],
        *,
        seen_checker: Callable[[list[str]], bool] | None = None,
    ) -> list[Listing]:
        region_osm_id = self.external_id(city)
        if region_osm_id is None:
            log.warning("City %r has no refs for %r", city.slug, self.source.key)
            return []

        region_id = f"R{region_osm_id}"

        supported = self.filter_categories(categories)
        if not supported:
            return []

        estate_types = self._estate_types_for(supported)
        if not estate_types:
            return []

        all_listings: list[Listing] = []
        offset = 0
        total_count = None

        for page in range(MAX_PAGES):
            try:
                response = self._gql_list_adverts(
                    region_id=region_id,
                    estate_types=estate_types,
                    limit=PAGE_SIZE,
                    offset=offset,
                )
            except Exception as e:
                log.exception("Bezrealitky page %d failed: %s", page, e)
                break

            if total_count is None:
                total_count = response.get("totalCount", 0)
                log.info("Bezrealitky %s: totalCount=%d", city.slug, total_count)

            raw_list = response.get("list", [])
            if not raw_list:
                break

            page_listings: list[Listing] = []
            for raw in raw_list:
                parsed = self._parse_advert(raw, city)
                if parsed is not None:
                    page_listings.append(parsed)
            all_listings.extend(page_listings)

            if seen_checker is not None:
                ids = [lst.id for lst in page_listings]
                if seen_checker(ids):
                    break

            offset += PAGE_SIZE
            if total_count is not None and offset >= total_count:
                break

            time.sleep(REQUEST_DELAY)

        log.info("Bezrealitky %s: %d listings", city.slug, len(all_listings))
        return all_listings

    def _gql_list_adverts(
        self,
        *,
        region_id: str,
        estate_types: list[str],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        variables = {
            "regionOsmIds": [region_id],
            "offerType": ["PRONAJEM"],
            "estateType": estate_types,
            "limit": limit,
            "offset": offset,
            "order": "TIMEORDER_DESC",
        }

        response = self._session.post(
            BEZREALITKY_GRAPHQL,
            json={"query": GQL_QUERY, "variables": variables},
            timeout=30,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://www.bezrealitky.cz",
                "Referer": "https://www.bezrealitky.cz/",
            },
        )

        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code} for offset={offset}")

        data = response.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")

        result: dict[str, Any] = data["data"]["listAdverts"]
        return result

    def _parse_advert(self, raw: dict[str, Any], city: City) -> Listing | None:
        advert_id = raw.get("id")
        if not advert_id:
            return None

        price = raw.get("price")
        charges = raw.get("charges") or 0
        currency = raw.get("currency", "CZK")
        price_str = self._format_price(price, charges, currency)

        location = raw.get("address") or raw.get("city") or city.name

        main_image = raw.get("mainImage") or {}
        photo = main_image.get("url", "")

        disposition_raw = raw.get("disposition")
        if disposition_raw is None:
            rooms = None
        else:
            rooms = DISPOSITION_MAP.get(str(disposition_raw), str(disposition_raw))
        if rooms in (None, "UNDEFINED", ""):
            rooms = None

        estate_type = raw.get("estateType", "BYT")
        category, category_icon, category_label = self._map_category(estate_type)

        title = self._build_title(raw, rooms)

        uri = raw.get("uri", "")
        link = f"https://www.bezrealitky.cz/nemovitosti-byty-domy/{uri}" if uri else ""

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
            area_m2=None,
            category=category,
            category_icon=category_icon,
            category_label=category_label,
            created_at=None,
            raw=raw,
        )

    def _estate_types_for(self, categories: list[str]) -> list[str]:
        mapping = self.source.config.get("estate_types", {})
        types = []
        for cat in categories:
            estate = mapping.get(cat)
            if estate and estate not in types:
                types.append(estate)
        return types

    @staticmethod
    def _format_price(price: int | None, charges: int, currency: str) -> str:
        if price is None:
            return "-"
        base = f"{price:,}".replace(",", " ")
        result = f"{base} {currency}"
        if charges:
            charges_str = f"{charges:,}".replace(",", " ")
            result += f" + {charges_str} {currency}"
        return result

    @staticmethod
    def _map_category(estate_type: str) -> tuple[str, str, str]:
        mapping = {
            "BYT": ("apartment", "🏢", "Byty"),
            "DUM": ("house", "🏠", "Domy"),
            "POZEMEK": ("land", "🌍", "Pozemky"),
            "KOMERCNI": ("commercial", "🏬", "Komerční"),
            "GARAZ": ("garage", "🚗", "Garáže"),
        }
        return mapping.get(estate_type, ("apartment", "🏢", "Byty"))

    @staticmethod
    def _build_title(raw: dict, rooms: str | None) -> str:
        """Формує заголовок: 'Pronájem bytu 2+kk, 38 m², Tachovské náměstí, Praha - Žižkov'."""
        # Перша частина — "Pronájem bytu 2+kk" (без коми між ними)
        estate = raw.get("estateType", "BYT")
        estate_cz = {"BYT": "bytu", "DUM": "domu"}.get(estate, "bytu")

        head = f"Pronájem {estate_cz}"
        if rooms:
            head += f" {rooms}"

        # Решта частин — через кому
        parts = [head]

        surface = raw.get("surface")
        if surface:
            parts.append(f"{surface} m²")

        # Скорочуємо address — беремо тільки першу частину (до коми)
        address = raw.get("address") or raw.get("city")
        if address:
            # "Smetanovo nábřeží, Vyškov - Vyškov, Jihomoravský kraj" → "Smetanovo nábřeží"
            # або "Střední, Brno - Ponava, Jihomoravský kraj" → "Střední"
            short_address = address.split(",")[0].strip()
            # Але якщо перша частина занадто коротка — беремо перші дві
            if len(short_address) < 5 and "," in address:
                short_address = ", ".join(p.strip() for p in address.split(",")[:2])
            parts.append(short_address)

        return ", ".join(parts)
