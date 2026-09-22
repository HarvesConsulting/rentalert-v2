from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers

# Тест 1: GET
r = cffi_requests.get(
    "https://www.openrent.co.uk/properties-to-rent/london",
    impersonate="chrome",
    headers=stealth_headers(),
    timeout=30,
)
print(f"GET: {r.status_code}, Size: {len(r.text)}")

# Тест 2: з слешем
r = cffi_requests.get(
    "https://www.openrent.co.uk/properties-to-rent/london/",
    impersonate="chrome",
    headers=stealth_headers(),
    timeout=30,
)
print(f"GET з слешем: {r.status_code}, Size: {len(r.text)}")

# Тест 3: з Referer
headers = stealth_headers()
headers["Referer"] = "https://www.openrent.co.uk/"
r = cffi_requests.get(
    "https://www.openrent.co.uk/properties-to-rent/london",
    impersonate="chrome",
    headers=headers,
    timeout=30,
)
print(f"GET з Referer: {r.status_code}, Size: {len(r.text)}")
