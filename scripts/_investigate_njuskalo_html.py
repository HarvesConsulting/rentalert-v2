"""Дослідження HTML-структури NJUSKALO.

Шукає селектори для парсингу оголошень.
"""

from __future__ import annotations

from bs4 import BeautifulSoup
from curl_cffi import requests

URL = "https://www.njuskalo.hr/iznajmljivanje-stanova/zagreb"


def main() -> None:
    print(f"📡 Fetch: {URL}\n")
    resp = requests.get(URL, impersonate="chrome", timeout=30)
    print(f"HTTP {resp.status_code}, size={len(resp.text)} байт\n")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Знаходимо ВСІ <li class="EntityList-item">
    items = soup.find_all("li", class_=lambda x: x and "EntityList-item" in x)
    print(f"🔍 Всього <li class='EntityList-item'>: {len(items)}\n")

    # Фільтруємо "FeaturedStore" (реклама)
    regular = [
        li
        for li in items
        if "EntityList-item--FeaturedStore" not in " ".join(li.get("class", []))
        and "EntityList-item--VauVau" not in " ".join(li.get("class", []))
    ]
    print(f"🔍 Звичайних: {len(regular)}\n")

    if not regular:
        print("❌ Немає звичайних оголошень")
        return

    # Беремо 3 звичайних
    for i, li in enumerate(regular[:3], 1):
        print(f"\n{'=' * 60}")
        print(f"📋 Оголошення #{i}")
        print(f"{'=' * 60}\n")
        print(li.prettify()[:4000])
        print(f"\n{'=' * 60}")

    # Аналізуємо перше
    first = regular[0]

    print("\n🔍 ПОСИЛАННЯ:\n")
    for a in first.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if "/oglas-" in href or "/nekretnine/" in href:
            print(f"  {text[:60]:60s} → {href}")

    print("\n🔍 ЦІНА (шукаю € / EUR):\n")
    for el in first.find_all(["span", "p", "div", "strong", "b"]):
        text = el.get_text(strip=True)
        if "€" in text or "EUR" in text or "eur" in text:
            classes = el.get("class", [])
            print(f"  [{el.name}] class={classes} → {text[:80]}")

    print("\n🔍 TITLE (h1-h4):\n")
    for h in first.find_all(["h1", "h2", "h3", "h4"]):
        classes = h.get("class", [])
        text = h.get_text(strip=True)
        print(f"  [{h.name}] class={classes} → {text[:100]}")

    print("\n🔍 IMG:\n")
    for img in first.find_all("img"):
        src = img.get("src", "")
        classes = img.get("class", [])
        print(f"  class={classes} → {src[:100]}")

    print("\n🔍 ЧАС (Published):\n")
    for el in first.find_all(["span", "time"]):
        text = el.get_text(strip=True)
        if ":" in text and (
            "2024" in text
            or "2025" in text
            or "2026" in text
            or "prije" in text.lower()
            or "Objavljen" in text
        ):
            classes = el.get("class", [])
            print(f"  [{el.name}] class={classes} → {text[:80]}")


if __name__ == "__main__":
    main()
