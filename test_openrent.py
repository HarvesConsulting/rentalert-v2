from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers

url = "https://www.openrent.co.uk/properties-to-rent/london"

r = cffi_requests.get(url, impersonate="chrome", headers=stealth_headers(), timeout=30)
print("Status:", r.status_code)
print("Size:", len(r.text))
print("First 500:", r.text[:500])
