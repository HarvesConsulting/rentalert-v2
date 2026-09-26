"""Знайти підкатегорії Imóveis в OLX.pt через API."""

from curl_cffi import requests as cffi_requests

# Спроба: OLX API має endpoint для отримання підкатегорій
urls = [
    "https://www.olx.pt/api/v1/categories/",
    "https://www.olx.pt/api/v1/categories/16/",
    "https://www.olx.pt/api/v1/categories/16/children/",
    "https://www.olx.pt/api/v1/offers/metadata/",
]

session = cffi_requests.Session(impersonate="chrome")

for url in urls:
    print(f"\n=== {url} ===")
    try:
        r = session.get(url, timeout=15)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            text = r.text
            if len(text) > 2000:
                print(f"Size: {len(text)}")
                print(text[:2000])
            else:
                print(text)
        else:
            print(f"Error: {r.text[:300]}")
    except Exception as e:
        print(f"Exception: {e}")
