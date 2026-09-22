from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers

url = "https://www.openrent.co.uk/properties-to-rent/london"
headers = stealth_headers()
headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

try:
    r = cffi_requests.get(
        url,
        headers=headers,
        impersonate="chrome",
        timeout=30,
    )
    print(f"Локальний запит (імітація Render): Status = {r.status_code}, Size = {len(r.text)}")
except Exception as e:
    print(f"Помилка: {e}")
