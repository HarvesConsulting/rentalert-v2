"""Знайти параметр фільтру для оренди в OLX.pt."""

from curl_cffi import requests as cffi_requests

url = "https://www.olx.pt/api/v1/offers/"
session = cffi_requests.Session(impersonate="chrome")

# Базові параметри
base = {
    "offset": 0,
    "limit": 5,
    "category_id": 16,  # Imóveis
    "region_id": 11,
    "sort_by": "created_at:desc",
}

# Можливі назви фільтрів для оренди
filter_names = [
    "filter_enum_transaction_type",
    "filter_enum_offer_type",
    "filter_enum_transaction",
    "filter_enum_rent_type",
    "filter_enum_deal_type",
    "filter_refiners",
    "filter_float_price:rent",
]

# Можливі значення
filter_values = ["rent", "arrendamento", "arrendar", "alugar", "for_rent", "1"]

for name in filter_names:
    for value in filter_values:
        params = {**base, name: value}
        try:
            r = session.get(url, params=params, timeout=15)
        except Exception as e:
            print(f"{name}={value}: ERROR {e}")
            continue

        if r.status_code == 200:
            items = r.json().get("data", []) or []
            titles = [it.get("title", "")[:50] for it in items[:3]]
            print(f"✅ {name}={value}: {len(items)} items")
            for t in titles:
                print(f"     - {t}")
        elif r.status_code == 400:
            # Спробуємо подивитись, чи є в помилці підказка
            try:
                err = r.json().get("error", {})
                msg = err.get("validation", [{}])[0].get("field", "")
                if msg:
                    print(f"❌ {name}={value}: 400 ({msg})")
            except:
                pass
