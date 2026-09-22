from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers

url = "https://www.rightmove.co.uk/property-to-rent/find.html?locationIdentifier=REGION%5E87490"

r = cffi_requests.get(url, impersonate="chrome", headers=stealth_headers(), timeout=30)
print("Status:", r.status_code)
print("Size:", len(r.text))

# Зберігаємо HTML у файл
with open("rightmove_page.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("💾 Збережено: rightmove_page.html")
