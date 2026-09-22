from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers

url = "https://www.openrent.co.uk/properties-to-rent/london"

r = cffi_requests.get(url, impersonate="chrome", headers=stealth_headers(), timeout=30)
print("Status:", r.status_code)
print("Size:", len(r.text))
print()

soup = BeautifulSoup(r.text, "html.parser")

# Шукаємо картки оголошень
# OpenRent зазвичай використовує div з класом "property-card" або подібним
# Пробуємо кілька варіантів
selectors = [
    "div.property-card",
    "div[class*='property']",
    "a[href*='/property-to-rent/']",
    "div[data-property-id]",
    "li[class*='property']",
]

for sel in selectors:
    items = soup.select(sel)
    print(f"{sel}: {len(items)} знайдено")
print()

# Знаходимо перше оголошення і показуємо структуру
# Шукаємо посилання на оголошення
links = soup.select("a[href*='/property-to-rent/']")
print(f"Всього посилань на оголошення: {len(links)}")
if links:
    first = links[0]
    print(f"Перше посилання: {first.get('href')}")
    print()
    # Показуємо батьківський елемент (картку)
    parent = first.find_parent("div", class_=True)
    if parent:
        print(f"Батько: {parent.name} class={parent.get('class')}")
        print()
        # Показуємо перші 2000 символів HTML картки
        print("HTML картки (перші 2000):")
        print(str(parent)[:2000])
