"""Збирає міста Молдови з оголошень 999.md.

Ідея:
  1. SearchAds для регіону → отримуємо ID оголошень.
  2. Для кожного ID — advert(id) → отримуємо feature(8).value (місто).
  3. feature(8).value — це вкладений об'єкт {value, translated, abbreviations}.
  4. Збираємо унікальні міста: {id, name, region_id, region_name}.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests

URL = "https://999.md/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "lang": "ru",
    "Origin": "https://999.md",
    "Referer": "https://999.md/",
}

SEARCH_QUERY = """
query SearchAds($input: Ads_SearchInput!) {
  searchAds(input: $input) {
    count
    ads { id }
  }
}
"""

ADVERT_QUERY = """
query GetAdvert($input: AdvertInput!) {
  advert(input: $input) {
    id
    city: feature(id: 8) { value }
    sector: feature(id: 9) { value }
  }
}
"""


def gql(query: str, variables: dict) -> dict:
    """POST-запит до 999.md GraphQL."""
    r = cffi_requests.post(
        URL,
        json={"query": query, "variables": variables},
        headers=HEADERS,
        impersonate="chrome",
        timeout=30,
    )
    return r.json()


def search_ads(region_id: int, limit: int = 50) -> list[int]:
    """Повертає список ID оголошень для регіону."""
    variables = {
        "input": {
            "source": "AD_SOURCE_DESKTOP_REDESIGN",
            "subCategoryId": 1406,  # будинки
            "filters": [
                {"filterId": 16, "features": [
                    {"featureId": 1, "optionIds": [912]},   # оренда
                ]},
                {"filterId": 8, "features": [
                    {"featureId": 7, "optionIds": [region_id]},   # region
                ]},
            ],
            "pagination": {"skip": 0, "limit": limit},
        }
    }

    data = gql(SEARCH_QUERY, variables)
    if "errors" in data:
        err = data["errors"][0].get("message", "")[:100]
        print(f"      ❌ searchAds errors: {err}")
        return []

    ads = data.get("data", {}).get("searchAds", {}).get("ads") or []
    return [int(ad["id"]) for ad in ads if ad.get("id")]


def get_advert_city(ad_id: int) -> tuple[int, str] | None:
    """Отримує (city_id, city_name) для оголошення.

    feature(8).value — це вкладений об'єкт:
      {"abbreviations": {}, "translated": "Кишинёв", "value": 13859}
    """
    data = gql(ADVERT_QUERY, {"input": {"id": str(ad_id)}})

    if "errors" in data:
        return None

    advert = data.get("data", {}).get("advert")
    if not advert:
        return None

    city_field = advert.get("city")
    if not isinstance(city_field, dict):
        return None

    value_obj = city_field.get("value")
    if not isinstance(value_obj, dict):
        return None

    city_id = value_obj.get("value")
    city_name = value_obj.get("translated") or ""

    if city_id is None:
        return None

    try:
        return int(city_id), str(city_name)
    except (TypeError, ValueError):
        return None


def load_regions() -> list[tuple[int, str]]:
    """Завантажує 44 регіони з md_999md_filters.json."""
    filters_path = Path("data/raw/md_999md_filters.json")
    if not filters_path.exists():
        print(f"❌ {filters_path} не знайдено")
        return []

    data = json.loads(filters_path.read_text(encoding="utf-8"))

    for f in data.get("features", []):
        if f.get("id") == 7:  # feature 7 = region
            regions: list[tuple[int, str]] = []
            for opt in f.get("options") or []:
                oid = opt.get("id")
                title = (opt.get("title") or {}).get("translated", "")
                if oid:
                    regions.append((int(oid), str(title)))
            return regions

    return []


def main() -> None:
    regions = load_regions()
    if not regions:
        return

    print(f"✅ Регіонів: {len(regions)}\n")

    cities: dict[int, dict] = {}

    for i, (region_id, region_name) in enumerate(regions, 1):
        print(f"[{i}/{len(regions)}] {region_name} ({region_id})")

        ad_ids = search_ads(region_id, limit=50)
        print(f"   → {len(ad_ids)} оголошень")

        for ad_id in ad_ids:
            try:
                result = get_advert_city(ad_id)
            except Exception as e:
                print(f"      ❌ advert {ad_id}: {e}")
                continue

            if not result:
                continue

            city_id, city_name = result

            if city_id in cities:
                continue

            cities[city_id] = {
                "id": city_id,
                "name": city_name,
                "region_id": region_id,
                "region_name": region_name,
                "example_ad": ad_id,
            }
            print(f"      ✅ {city_id} — {city_name}")

            time.sleep(0.05)

        time.sleep(0.2)

    print(f"\n📊 Всього унікальних міст: {len(cities)}")

    # Зберегти
    out = Path("data/raw/md_999md_cities_from_ads.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(list(cities.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"💾 Збережено: {out}")

    # Показати всі знайдені
    print("\nУсі знайдені міста:")
    for c in sorted(cities.values(), key=lambda x: x["name"]):
        print(f"  {c['id']:>6} | {c['name']:<25} | {c['region_name']}")


if __name__ == "__main__":
    main()
