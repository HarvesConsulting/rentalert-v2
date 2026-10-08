"""Перевіряє, чи OLX API передає площу у params."""

from __future__ import annotations

from curl_cffi import requests as cffi_requests

URL = "https://www.olx.ua/api/v1/offers/"
HEADERS = {
    "Accept": "application/json",
    "Referer": "https://www.olx.ua/",
}


def main() -> None:
    r = cffi_requests.get(
        URL,
        params={
            "offset": 0,
            "limit": 3,
            "city_id": 96,          # Київ
            "category_id": 1760,    # Квартири (оренда)
            "sort_by": "created_at:desc",
        },
        headers=HEADERS,
        impersonate="chrome",
        timeout=30,
    )

    print(f"HTTP {r.status_code}\n")

    if r.status_code != 200:
        print(r.text[:500])
        return

    data = r.json()
    items = data.get("data") or []

    print(f"Отримано оголошень: {len(items)}\n")

    for i, item in enumerate(items[:3], 1):
        print(f"=== [{i}] id={item.get('id')} ===")
        print(f"TITLE: {item.get('title')!r}")
        print()

        params = item.get("params") or []
        print(f"PARAMS ({len(params)}):")
        for p in params:
            key = p.get("key", "")
            name = p.get("name", "")
            value = p.get("value")
            print(f"  key={key!r:20} name={name!r:25} value={value!r}")

        print()

        # Шукаємо "area" / "m" / "площа"
        print("ПОШУК ПЛОЩІ:")
        for p in params:
            key = (p.get("key") or "").lower()
            name = (p.get("name") or "").lower()
            if key == "m" or "площад" in name or "powierzchnia" in name:
                print(f"  ✅ ЗНАЙДЕНО: {p.get('key')} = {p.get('value')}")

        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
