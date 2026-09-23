"""Перевірка: чи різні ID при різних offset."""

from curl_cffi import requests as cffi_requests

from rentalert.parsers.stealth import stealth_headers


def fetch_olx(offset: int) -> list[int]:
    """Запит до OLX API, повертає список ID."""
    params = {
        "offset": offset,
        "limit": 40,
        "city_id": 268,
        "category_id": 1760,
        "sort_by": "created_at:desc",
    }
    r = cffi_requests.get(
        "https://www.olx.ua/api/v1/offers/",
        params=params,
        impersonate="chrome",
        headers=stealth_headers(),
        timeout=30,
    )
    if r.status_code != 200:
        return []
    data = r.json()
    return [item.get("id") for item in data.get("data", []) if item.get("id")]


def main() -> None:
    all_ids: set[int] = set()

    for offset in [0, 52, 104, 156, 208]:
        ids = fetch_olx(offset)
        new_ids = [i for i in ids if i not in all_ids]
        all_ids.update(ids)
        print(f"offset={offset:4}: отримано {len(ids):3}, нових {len(new_ids):3}")
        print(f"  перші 3: {ids[:3]}")
        print()


if __name__ == "__main__":
    main()
