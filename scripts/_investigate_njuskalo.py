"""Дослідження структури NJUSKALO для парсера.

Шукає всі міста/жупанії у лівому меню.
"""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

BASE = "https://www.njuskalo.hr"
URL = f"{BASE}/iznajmljivanje-stanova"


def main() -> None:
    print(f"📡 Fetch: {URL}")
    resp = requests.get(URL, impersonate="chrome", timeout=30)
    print(f"HTTP {resp.status_code}, size={len(resp.text)} байт")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Шукаємо всі <a> з посиланнями на iznajmljivanje-stanova/{slug}
    links: dict[str, str] = {}  # slug → назва

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)

        # Ігноруємо порожні
        if not text:
            continue

        # Перевіряємо чи це посилання на місто/жупанію
        if "/iznajmljivanje-stanova/" in href:
            path = urlparse(href).path.strip("/")
            parts = path.split("/")
            if len(parts) == 2 and parts[0] == "iznajmljivanje-stanova":
                slug = parts[1]
                if slug not in links:
                    links[slug] = text

    print(f"\n📍 Знайдено {len(links)} міст/жупаній:\n")
    for slug, name in sorted(links.items()):
        print(f"  {slug:30s} → {name}")


if __name__ == "__main__":
    main()
