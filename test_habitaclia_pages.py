"""Перевірка пагінації Habitaclia для Barcelona.

URL-патерн:
  Сторінка 1: https://www.habitaclia.com/alquiler-barcelona.htm
  Сторінка 2: https://www.habitaclia.com/alquiler-barcelona-2.htm
  Сторінка 3: https://www.habitaclia.com/alquiler-barcelona-3.htm
  ...
"""

import re

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import human_delay, stealth_headers

BASE_SLUG = "barcelona"
BASE_URL = "https://www.habitaclia.com"


def make_page_url(slug: str, page: int) -> str:
    """Формує URL сторінки."""
    if page == 1:
        return f"{BASE_URL}/alquiler-{slug}.htm"
    return f"{BASE_URL}/alquiler-{slug}-{page}.htm"


def extract_ids(html: str) -> list[str]:
    """Витягує ID оголошень з HTML."""
    soup = BeautifulSoup(html, "html.parser")
    ids: list[str] = []
    for art in soup.find_all("article"):
        link = art.find("a", attrs={"data-panot-component": "link-box-link"})
        if not link:
            continue
        href = link.get("href", "")
        m = re.search(r"/i(\d+)\.htm", href)
        if m:
            ids.append(m.group(1))
    return ids


def main() -> None:
    all_ids: set[str] = set()

    for page in range(1, 8):
        url = make_page_url(BASE_SLUG, page)
        try:
            r = cffi_requests.get(
                url,
                impersonate="chrome",
                headers=stealth_headers(),
                timeout=30,
            )
        except Exception as e:
            print(f"Сторінка {page}: ERROR {e}")
            continue

        if r.status_code != 200:
            print(f"Сторінка {page}: HTTP {r.status_code} — СТОП")
            break

        ids = extract_ids(r.text)
        new_ids = [i for i in ids if i not in all_ids]
        all_ids.update(ids)

        print(f"Сторінка {page}: {len(ids)} оголошень, з них нових: {len(new_ids)}")
        print(f"  URL: {url}")

        if not ids:
            print("  Порожня сторінка — СТОП")
            break

        if not new_ids:
            print("  Всі ID вже бачили — СТОП (догнали)")
            break

        human_delay(1.5, 3.0)

    print()
    print(f"Всього унікальних ID: {len(all_ids)}")


if __name__ == "__main__":
    main()
