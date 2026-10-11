"""Мапінг slug-ів міст для Storia.ro — для ВСІХ міст.

Мапить за name (не за slug), підтримує resume, захист від бану.

Запуск:
    python scripts/map_storia_slugs.py            # продовжити з місця зупинки
    python scripts/map_storia_slugs.py --restart  # почати з нуля
    python scripts/map_storia_slugs.py --limit 100  # обробити тільки 100

Результат:
    scripts/storia_slug_map.json (оновлюється після кожного міста)
    scripts/storia_slug_map.progress (службовий файл — індекс останнього міста)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

ROOT = Path(__file__).resolve().parent.parent
CITIES_FILE = ROOT / "data" / "cities" / "ro.json"
OUT_FILE = ROOT / "scripts" / "storia_slug_map.json"
PROGRESS_FILE = ROOT / "scripts" / "storia_slug_map.progress"

BASE = "https://www.storia.ro/ro/rezultate/inchiriere/apartament"

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Referer": "https://www.storia.ro/",
}

MIN_CARDS = 3
DELAY = 2.0
MAX_CONSECUTIVE_ERRORS = 20

# Ручні override для міст, які не знаходяться автоматично
MANUAL_OVERRIDES: dict[str, str] = {
    "cluj-napoca": "cluj/cluj--napoca",
}


def slugify(text: str) -> str:
    """'Cluj-Napoca' → 'cluj-napoca', 'Bucuresti - Ilfov' → 'bucuresti-ilfov'."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def try_url(session, url: str) -> tuple[bool, int]:
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
    except Exception:
        return False, -1
    if r.status_code != 200:
        return False, r.status_code
    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.select('article[data-sentry-component="AdvertCard"]')
    return len(cards) >= MIN_CARDS, len(cards)


def candidates(city: dict) -> list[str]:
    """Усі можливі URL-варіанти для міста."""
    slug = city["slug"]

    # 0. Ручний override
    if slug in MANUAL_OVERRIDES:
        return [f"{BASE}/{MANUAL_OVERRIDES[slug]}"]

    name = city["name"]
    region = city.get("region", "")

    name_slug = slugify(name)
    region_slug = slugify(region) if region else ""
    # Варіант з подвійним дефісом (для Cluj-Napoca та подібних)
    name_slug_2x = name_slug.replace("-", "--")

    urls: list[str] = []

    # 1. /name-slug
    if name_slug:
        urls.append(f"{BASE}/{name_slug}")

    # 2. /slug з ro.json (для priority — там slug = name-slug)
    if slug and slug != name_slug and not slug.startswith("olx_ro_"):
        urls.append(f"{BASE}/{slug}")

    # 3. /region/name
    if region_slug and region_slug != name_slug:
        urls.append(f"{BASE}/{region_slug}/{name_slug}")

    # 4. /region/name--slug (подвійний дефіс)
    if region_slug and name_slug_2x != name_slug:
        urls.append(f"{BASE}/{region_slug}/{name_slug_2x}")

    # Дедуплікація
    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_progress() -> int:
    if not PROGRESS_FILE.exists():
        return 0
    try:
        return int(PROGRESS_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return 0


def save_progress(idx: int) -> None:
    PROGRESS_FILE.write_text(str(idx), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true", help="почати з нуля")
    parser.add_argument("--limit", type=int, default=0, help="обробити N міст і зупинитись")
    args = parser.parse_args()

    if args.restart:
        if OUT_FILE.exists():
            OUT_FILE.unlink()
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        print("Рестарт: очищено прогрес і звіт")

    cities_data = json.loads(CITIES_FILE.read_text(encoding="utf-8"))
    cities = cities_data["cities"]
    total = len(cities)

    print(f"Всього міст у ro.json: {total}")

    result = load_json(OUT_FILE)
    start_idx = load_progress()

    print(f"Продовжую з індексу {start_idx} (оброблено {len(result)} міст)")
    print(f"Затримка між містами: {DELAY} сек")

    if args.limit:
        print(f"Ліміт: {args.limit} міст за цей запуск")

    session = cffi_requests.Session(impersonate="chrome124")
    consecutive_errors = 0
    found = sum(1 for v in result.values() if v.get("storia_slug"))
    processed_this_run = 0

    try:
        for i in range(start_idx, total):
            city = cities[i]
            slug = city["slug"]
            name = city["name"]

            # Вже оброблене — пропускаємо
            if slug in result and result[slug].get("checked"):
                continue

            ok = False
            working = None
            tried: list[dict] = []

            for url in candidates(city):
                success, cards = try_url(session, url)
                tried.append({"url": url, "ok": success, "cards": cards})

                if cards in (403, 429):
                    consecutive_errors += 1
                    print(f"  ⚠️  HTTP {cards} — можливий бан (підряд: {consecutive_errors})")
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        print(f"\n❌ Стоп: {MAX_CONSECUTIVE_ERRORS} помилок підряд")
                        save_json(OUT_FILE, result)
                        save_progress(i)
                        sys.exit(2)
                elif cards == -1:
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0

                if success:
                    ok = True
                    working = url.replace(f"{BASE}/", "")
                    found += 1
                    break

                time.sleep(DELAY)

            result[slug] = {
                "name": name,
                "storia_slug": working,
                "url": f"{BASE}/{working}" if working else None,
                "checked": True,
                "tried": tried,
            }

            save_json(OUT_FILE, result)
            save_progress(i + 1)

            processed_this_run += 1

            # Лог: кожне знайдене АБО кожне 10-те
            if ok or processed_this_run % 10 == 0:
                percent = (i + 1) / total * 100
                mark = "✅" if ok else "· "
                print(
                    f"  [{i + 1}/{total}] ({percent:.1f}%) {mark} {name} → {working or '—'} "
                    f"[знайдено: {found}]"
                )

            if args.limit and processed_this_run >= args.limit:
                print(f"\nДосягнуто ліміт {args.limit} — вихід")
                break

    except KeyboardInterrupt:
        print("\n\n⏸ Зупинено користувачем (Ctrl+C)")
        save_json(OUT_FILE, result)
        save_progress(i)
        print(f"Прогрес збережено на індексі {i}")

    print()
    print(f"{'=' * 60}")
    print(f"Оброблено за цей запуск: {processed_this_run}")
    print(f"Всього знайдено storia_slug: {found}")
    print(f"Звіт: {OUT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
