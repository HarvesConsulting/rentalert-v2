"""Швидкий тест Parser999Md: searchAds + advert + fetch."""
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from rentalert.catalog.models import City, Source
from rentalert.parsers.md999 import Parser999Md


def main() -> None:
    src = Source(
        key="999md",
        country="md",
        name="999.md",
        icon="🇲🇩",
        kind="999md",
        base_url="https://999.md",
        enabled_by_default=True,
        categories=("apartment", "house"),
        config={},
    )
    p = Parser999Md(src)

    city = City(
        slug="chisinau",
        country="md",
        name="Chișinău",
        region="Chișinău",
        priority=True,
        refs={"999md": 13859},
    )

    # ── 1. searchAds ──
    print("\n" + "=" * 60)
    print("1. searchAds (5 шт.)")
    print("=" * 60)
    res = p._gql_search(
        subcategory_id=1404, location_id=13859, skip=0, limit=5,
    )
    if not res:
        print("❌ searchAds повернув None")
        return
    print(f"count = {res.get('count')}")
    ads = res.get("ads") or []
    print(f"ads у відповіді: {len(ads)}")
    for ad in ads[:3]:
        print(f"   {ad.get('id')} — {(ad.get('title') or '')[:60]}")

    if not ads:
        print("❌ ads порожній")
        return

    # ── 2. advert (перший) ──
    print("\n" + "=" * 60)
    print("2. advert — деталі першого")
    print("=" * 60)
    first = p._fetch_advert(ads[0], city, "apartment")
    if first is None:
        print("❌ _fetch_advert повернув None")
        return
    print(f"id:       {first.id}")
    print(f"title:    {first.title}")
    print(f"price:    {first.price}")
    print(f"location: {first.location}")
    print(f"link:     {first.link}")
    print(f"photo:    {first.photo}")
    print(f"rooms:    {first.rooms}")
    print(f"category: {first.category} {first.category_icon} {first.category_label}")
    print(f"created:  {first.created_at}")

    # ── 2b. RAW advert (дебаг posted) ──
    print("\n" + "=" * 60)
    print("2b. RAW advert (для дебагу posted)")
    print("=" * 60)
    query_raw = """
    query GetAdvert($input: AdvertInput!) {
      advert(input: $input) {
        id
        title
        posted
      }
    }
    """
    resp = p._post(query_raw, {"input": {"id": str(ads[0]["id"])}})
    print(json.dumps(resp, indent=2, ensure_ascii=False))

    # ── 3. Повний fetch однієї категорії ──
    print("\n" + "=" * 60)
    print("3. _fetch_category (apartment, обмежено 3 сторінки)")
    print("=" * 60)
    import rentalert.parsers.md999 as md999_mod
    original_max = md999_mod.MAX_PAGES
    md999_mod.MAX_PAGES = 3
    try:
        lst = p._fetch_category(
            subcategory_id=1404,
            location_id=13859,
            city=city,
            category="apartment",
        )
        print(f"\n✅ Отримано оголошень: {len(lst)}")
        if lst:
            print("\nПерші 3:")
            for item in lst[:3]:
                print(f"   {item.title[:70]}")
                print(f"      {item.price} | {item.location}")
    finally:
        md999_mod.MAX_PAGES = original_max

    # ── 4. seen_checker (симуляція) ──
    print("\n" + "=" * 60)
    print("4. seen_checker — симуляція варіанта A")
    print("=" * 60)
    calls: list[int] = []

    def fake_all_seen(ids: list[str]) -> bool:
        calls.append(len(ids))
        return True   # "усі вже в БД"

    lst = p._fetch_category(
        subcategory_id=1404,
        location_id=13859,
        city=city,
        category="apartment",
        seen_checker=fake_all_seen,
    )
    print(f"seen_checker викликано: {len(calls)} разів, розміри: {calls}")
    print(f"Отримано оголошень: {len(lst)}")
    if calls == [30] and len(lst) == 0:
        print("✅ seen_checker працює як варіант A (стоп на 1-й сторінці)")
    else:
        print("⚠️  Перевірте логіку seen_checker")

    print("\n" + "=" * 60)
    print("ГОТОВО")
    print("=" * 60)


if __name__ == "__main__":
    main()
