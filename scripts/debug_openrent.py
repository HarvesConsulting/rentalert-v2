"""Діагностика OpenRent — чому 405?

Використовуємо ТІЛЬКИ реальні назви impersonate з curl_cffi 0.16.3.
"""

from curl_cffi import requests as cffi_requests

URL = "https://www.openrent.co.uk/properties-to-rent/london"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.openrent.co.uk/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Тільки ті, що точно є в 0.16.3
IMPERSONATIONS = [
    "chrome131",  # поточний у парсері
    "chrome136",  # новіший
    "chrome142",  # ще новіший
    "chrome145",
    "chrome146",
    "chrome150",  # найновіший
    "firefox135",
    "firefox144",
    "firefox147",
    "safari180",
    "safari184",
    "safari260",
]

for imp in IMPERSONATIONS:
    print(f"\n=== impersonate={imp} ===")
    try:
        r = cffi_requests.get(
            URL,
            impersonate=imp,
            headers=HEADERS,
            timeout=20,
        )
        print(f"  HTTP:         {r.status_code}")
        print(f"  Content-Type: {r.headers.get('content-type')}")
        print(f"  Server:       {r.headers.get('server')}")
        print(f"  Body[:200]:   {r.text[:200]!r}")
    except Exception as e:
        print(f"  ❌ {e}")
