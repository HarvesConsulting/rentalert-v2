"""Перевіряє _extract_area на реальній картці Pisos."""

from bs4 import BeautifulSoup
from curl_cffi import requests

from rentalert.parsers.pisos import PisosParser


def main() -> None:
    r = requests.get(
        "https://www.pisos.com/alquiler/pisos-madrid/",
        impersonate="chrome",
        timeout=30,
    )
    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.find_all("div", class_="ad-preview")

    print(f"Карток: {len(cards)}\n")

    card = cards[0] if cards else None
    if not card:
        print("Немає карток")
        return

    # 1. Текст картки
    print("=== TEXT картки ===")
    text = card.get_text(" | ", strip=True)
    print(text[:500])
    print()

    # 2. _extract_area
    print("=== _extract_area ===")
    print(f"Результат: {PisosParser._extract_area(card)}")
    print()

    # 3. .ad-preview__char
    print("=== .ad-preview__char ===")
    chars = card.select(".ad-preview__char")
    print(f"Елементів: {len(chars)}")
    for i, c in enumerate(chars):
        print(f"  [{i}] {c.get_text(strip=True)!r}")
        print(f"      HTML: {str(c)[:150]}")
    print()

    # 4. Пошук "m²" у тексті
    print("=== Пошук 'm²' ===")
    import re

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m", text)
    print(f"Regex match: {m.group(0) if m else 'НЕМАЄ'}")


if __name__ == "__main__":
    main()
