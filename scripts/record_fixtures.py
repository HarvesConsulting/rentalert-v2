"""Записує реальні відповіді з джерел у tests/fixtures/ для тестів.

Запуск:
    python scripts/record_fixtures.py

Створює:
    tests/fixtures/olx_ua_response.json
    tests/fixtures/dimria_search_response.json
    tests/fixtures/dimria_info_response.json
    tests/fixtures/kleinanzeigen_page.html
    tests/fixtures/habitaclia_page.html
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# OLX.ua — реальний API
# ─────────────────────────────────────────────────────────────

def record_olx_ua() -> None:
    """OLX.ua API: 40 оголошень для Києва, категорія «Квартири»."""
    print("📡 OLX.ua — fetch...")

    url = "https://www.olx.ua/api/v1/offers/"
    params = {
        "offset": 0,
        "limit": 40,
        "city_id": 268,  # Київ
        "category_id": 1760,  # Квартири
        "sort_by": "created_at:desc",
    }

    session = cffi_requests.Session(impersonate="chrome")
    try:
        response = session.get(url, params=params, timeout=30)
    except Exception as e:
        print(f"  ❌ Помилка: {e}")
        return

    print(f"  HTTP {response.status_code}")

    if response.status_code != 200:
        print(f"  ⚠️ Пропускаємо (не 200): {response.text[:200]}")
        return

    data = response.json()
    items = data.get("data", [])
    print(f"  Отримано {len(items)} оголошень")

    out = FIXTURES / "olx_ua_response.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Збережено в {out}")


# ─────────────────────────────────────────────────────────────
# DIM.RIA — потребує API-ключа
# ─────────────────────────────────────────────────────────────

def record_dimria() -> None:
    """DIM.RIA: search + info одного оголошення."""
    print("\n📡 DIM.RIA — fetch...")

    api_key = os.environ.get("DIMRIA_API_KEY", "")
    if not api_key:
        print("  ⚠️ DIMRIA_API_KEY не встановлено — пропускаємо")
        return

    base = "https://developers.ria.com/dom"

    # 1. Search
    try:
        response = cffi_requests.get(
            f"{base}/search",
            params={
                "api_key": api_key,
                "category": 1,
                "realty_type": 2,
                "operation_type": 1,  # ← оренда (не 2!)
                "city_id": 10,        # Київ
                "limit": 20,
            },
            timeout=25,
        )
    except Exception as e:
        print(f"  ❌ Search: {e}")
        return

    print(f"  Search HTTP {response.status_code}")

    if response.status_code != 200:
        print(f"  ⚠️ Пропускаємо: {response.text[:200]}")
        return

    search_data = response.json()
    items = search_data.get("items", [])
    print(f"  Отримано {len(items)} ID")

    out = FIXTURES / "dimria_search_response.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(search_data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Search → {out}")

    # 2. Info (перший ID)
    if not items:
        print("  ⚠️ Немає ID — info не записуємо")
        return

    time.sleep(3)  # rate limit
    realty_id = items[0]

    try:
        response = cffi_requests.get(
            f"{base}/info/{realty_id}",
            params={"api_key": api_key},
            timeout=25,
        )
    except Exception as e:
        print(f"  ❌ Info: {e}")
        return

    print(f"  Info HTTP {response.status_code}")

    if response.status_code != 200:
        print(f"  ⚠️ Info: {response.text[:200]}")
        return

    info_data = response.json()
    out = FIXTURES / "dimria_info_response.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(info_data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ Info → {out}")


# ─────────────────────────────────────────────────────────────
# Kleinanzeigen — HTML
# ─────────────────────────────────────────────────────────────

def record_kleinanzeigen() -> None:
    """Kleinanzeigen: HTML-сторінка Берліна, категорія «Wohnungen»."""
    print("\n📡 Kleinanzeigen — fetch...")

    url = "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331"

    try:
        response = cffi_requests.get(url, impersonate="chrome", timeout=30)
    except Exception as e:
        print(f"  ❌ Помилка: {e}")
        return

    print(f"  HTTP {response.status_code}")

    if response.status_code != 200:
        print(f"  ⚠️ Пропускаємо: {response.text[:200]}")
        return

    out = FIXTURES / "kleinanzeigen_page.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"  ✅ Збережено в {out} ({len(response.text)} байт)")


# ─────────────────────────────────────────────────────────────
# Habitaclia — HTML
# ─────────────────────────────────────────────────────────────

def record_habitaclia() -> None:
    """Habitaclia: HTML-сторінка Мадрида."""
    print("\n📡 Habitaclia — fetch...")

    url = "https://www.habitaclia.com/alquiler-madrid.htm"

    try:
        response = cffi_requests.get(url, impersonate="chrome", timeout=30)
    except Exception as e:
        print(f"  ❌ Помилка: {e}")
        return

    print(f"  HTTP {response.status_code}")

    if response.status_code != 200:
        print(f"  ⚠️ Пропускаємо: {response.text[:200]}")
        return

    out = FIXTURES / "habitaclia_page.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"  ✅ Збережено в {out} ({len(response.text)} байт)")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Запис фікстур у {FIXTURES}\n")

    record_olx_ua()
    time.sleep(2)
    record_dimria()
    time.sleep(2)
    record_kleinanzeigen()
    time.sleep(2)
    record_habitaclia()

    print("\n✅ Готово.")


if __name__ == "__main__":
    main()
