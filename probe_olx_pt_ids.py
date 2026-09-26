"""Перебір category_id і region_id для OLX.pt."""

from curl_cffi import requests as cffi_requests

url = "https://www.olx.pt/api/v1/offers/"

# Список можливих ID (з HTML вище + здогадки)
candidate_category_ids = [11, 14, 362, 4800, 4918]

# Перебір для Porto Santo (з URL: portosanto)
# Можливі region_id: не знаємо, спробуємо кілька
candidate_region_ids = [11, 14, 362, 4800, 4918, 100, 1000]

session = cffi_requests.Session(impersonate="chrome")

for cat_id in candidate_category_ids:
    for reg_id in candidate_region_ids:
        params = {
            "offset": 0,
            "limit": 3,
            "category_id": cat_id,
            "region_id": reg_id,
            "sort_by": "created_at:desc",
        }
        try:
            r = session.get(url, params=params, timeout=15)
        except Exception as e:
            print(f"cat={cat_id}, reg={reg_id}: ERROR {e}")
            continue

        if r.status_code == 200:
            data = r.json()
            items = data.get("data", []) or []
            titles = [it.get("title", "")[:50] for it in items[:3]]
            print(f"✅ cat={cat_id}, reg={reg_id}: 200 OK, {len(items)} items")
            for t in titles:
                print(f"     - {t}")
        elif r.status_code == 400:
            # Просто невірний ID — не показуємо
            continue
        else:
            print(f"❌ cat={cat_id}, reg={reg_id}: {r.status_code}")

print("\nГотово.")
