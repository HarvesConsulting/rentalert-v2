"""Перевірка: який size працює для Bien'ici API."""

import json

from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers


def test_size(size: int) -> tuple[int, int]:
    """Повертає (отримано, total)."""
    filters = {
        "size": size,
        "from": 0,
        "filterType": "rent",
        "propertyType": ["flat"],
        "page": 1,
        "sortBy": "relevance",
        "onTheMarket": [True],
        "zoneIdsByTypes": {"zoneIds": ["-7444"]},  # Paris
    }
    r = cffi_requests.get(
        "https://www.bienici.com/realEstateAds.json",
        params={"filters": json.dumps(filters)},
        impersonate="chrome",
        headers=stealth_headers(),
        timeout=30,
    )
    data = r.json()
    return len(data.get("realEstateAds", [])), data.get("total", 0)


def main() -> None:
    for size in [24, 50, 100, 200, 500]:
        try:
            got, total = test_size(size)
            print(f"size={size:4}: отримано {got:3}, total={total}")
        except Exception as e:
            print(f"size={size:4}: ERROR {e}")


if __name__ == "__main__":
    main()
