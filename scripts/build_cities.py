"""Генерація каталогу міст для RentAlert v2.

Читає raw-дані з data/raw/ та overrides з data/overrides/,
об'єднує OLX + DIM.RIA для UA, конвертує у формат v2,
записує data/cities/*.json.

Запуск:
    python scripts/build_cities.py
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
OVERRIDES = ROOT / "data" / "overrides"
OUT = ROOT / "data" / "cities"


# ─────────────────────────────────────────────────────────────
# Утиліти
# ─────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def norm(s: str | None) -> str:
    """Нормалізація: lower + видалення діакритики."""
    if not s:
        return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def norm_region(s: str | None) -> str:
    """Нормалізація регіону: без слова 'область', ' Oblast' тощо."""
    s = norm(s)
    for suffix in [" oblast", " область", " обл.", " region"]:
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    return s


def _priority_slug(name: str, priority_map: dict, fallback: str) -> tuple[str, bool]:
    """Повертає (slug, is_priority). Якщо назва в priority_map → override slug."""
    for prio_slug, prio_name in priority_map.items():
        if norm(prio_name) == norm(name):
            return prio_slug, True
    return fallback, False


def dedupe(cities: list[dict]) -> list[dict]:
    """Прибирає дублікати за slug і за (norm(name), norm_region)."""
    seen_slug: dict[str, int] = {}
    seen_key: dict[tuple[str, str], int] = {}
    result: list[dict] = []

    for c in cities:
        # 1. Slug має бути унікальним
        if c["slug"] in seen_slug:
            idx = seen_slug[c["slug"]]
            existing = result[idx]
            # Зливаємо refs
            for k, v in c["refs"].items():
                existing["refs"].setdefault(k, v)
            continue

        # 2. (name, region) має бути унікальним
        key = (norm(c["name"]), norm_region(c.get("region", "")))
        if key in seen_key:
            idx = seen_key[key]
            existing = result[idx]
            if c.get("priority") and not existing.get("priority"):
                # Замінюємо на priority-версію
                seen_slug.pop(existing["slug"], None)
                result[idx] = c
                seen_slug[c["slug"]] = idx
            else:
                # Зливаємо refs
                for k, v in c["refs"].items():
                    existing["refs"].setdefault(k, v)
            continue

        seen_slug[c["slug"]] = len(result)
        seen_key[key] = len(result)
        result.append(c)

    return result


# ─────────────────────────────────────────────────────────────
# UA — об'єднання OLX + DIM.RIA
# ─────────────────────────────────────────────────────────────


def build_ua() -> dict:
    olx_raw = load_json(RAW / "ua_olx.json")
    dimria_raw = load_json(RAW / "ua_dimria.json")
    priority = load_json(OVERRIDES / "priority_ua.json")

    # Два індекси DIM.RIA
    dimria_by_key: dict[tuple[str, str], int] = {}
    dimria_by_name: dict[str, list[int]] = {}
    for d in dimria_raw:
        key = (norm(d["name"]), norm_region(d.get("state_name")))
        dimria_by_key.setdefault(key, d["id"])
        dimria_by_name.setdefault(norm(d["name"]), []).append(d["id"])

    used_dimria_ids: set[int] = set()
    cities: list[dict] = []

    # ── Крок 1: OLX ──
    for o in olx_raw:
        name = o["city_name"]
        region = o.get("region_name", "")
        olx_id = o["city_id"]

        slug, is_priority = _priority_slug(name, priority, f"olx_ua_{olx_id}")

        if is_priority:
            # Priority: матчимо за назвою
            dimria_ids = dimria_by_name.get(norm(name), [])
            dimria_id = dimria_ids[0] if dimria_ids else None
        else:
            key = (norm(name), norm_region(region))
            dimria_id = dimria_by_key.get(key)

        refs = {"olx_ua": olx_id}
        if dimria_id:
            refs["dimria"] = dimria_id
            used_dimria_ids.add(dimria_id)

        cities.append(
            {
                "slug": slug,
                "name": name,
                "region": region,
                "priority": is_priority,
                "refs": refs,
            }
        )

    # ── Крок 2: решта DIM.RIA ──
    used_names: set[str] = {norm(c["name"]) for c in cities if c.get("priority")}

    for d in dimria_raw:
        if d["id"] in used_dimria_ids:
            continue
        if norm(d["name"]) in used_names:
            continue
        cities.append(
            {
                "slug": f"dimria_{d['id']}",
                "name": d["name"],
                "region": d.get("state_name", ""),
                "priority": False,
                "refs": {"dimria": d["id"]},
            }
        )

    cities = dedupe(cities)
    cities.sort(key=lambda c: (not c["priority"], c["name"]))

    print(
        f"  UA: {len(cities)} міст "
        f"({sum(1 for c in cities if c['priority'])} priority, "
        f"{sum(1 for c in cities if 'dimria' in c['refs'])} з DIM.RIA)"
    )

    return {"country": "ua", "cities": cities}


# ─────────────────────────────────────────────────────────────
# PL — OLX.pl
# ─────────────────────────────────────────────────────────────


def build_pl() -> dict:
    olx_raw = load_json(RAW / "pl_olx.json")
    priority = load_json(OVERRIDES / "priority_pl.json")

    cities = []
    for o in olx_raw:
        name = o["city_name"]
        olx_id = o["city_id"]
        slug, is_priority = _priority_slug(name, priority, f"olx_pl_{olx_id}")
        cities.append(
            {
                "slug": slug,
                "name": name,
                "region": o.get("region_name", ""),
                "priority": is_priority,
                "refs": {"olx_pl": olx_id},
            }
        )

    cities = dedupe(cities)
    cities.sort(key=lambda c: (not c["priority"], c["name"]))
    print(f"  PL: {len(cities)} міст ({sum(1 for c in cities if c['priority'])} priority)")
    return {"country": "pl", "cities": cities}


# ─────────────────────────────────────────────────────────────
# PT — регіони з override
# ─────────────────────────────────────────────────────────────


def build_pt() -> dict:
    pt_override = load_json(OVERRIDES / "priority_pt.json")

    cities = []
    for slug, info in pt_override.items():
        cities.append(
            {
                "slug": slug,
                "name": info["name"],
                "region": "",
                "priority": info.get("priority", False),
                "refs": {"olx_pt": info["region_id"]},
            }
        )

    cities.sort(key=lambda c: (not c["priority"], c["name"]))
    print(f"  PT: {len(cities)} регіонів ({sum(1 for c in cities if c['priority'])} priority)")
    return {"country": "pt", "cities": cities}


# ─────────────────────────────────────────────────────────────
# RO — OLX.ro (priority вже в raw)
# ─────────────────────────────────────────────────────────────


def build_ro() -> dict:
    olx_raw = load_json(RAW / "ro_olx.json")
    priority = load_json(OVERRIDES / "priority_ro.json")

    cities = []
    for o in olx_raw:
        olx_id = o["olx_city_id"]
        name = o["name"]
        slug, _ = _priority_slug(name, priority, f"olx_ro_{olx_id}")
        cities.append(
            {
                "slug": slug,
                "name": name,
                "region": o.get("region", ""),
                "priority": o.get("priority", False),
                "refs": {"olx_ro": olx_id},
            }
        )

    cities = dedupe(cities)
    cities.sort(key=lambda c: (not c["priority"], c["name"]))
    print(f"  RO: {len(cities)} міст ({sum(1 for c in cities if c['priority'])} priority)")
    return {"country": "ro", "cities": cities}


# ─────────────────────────────────────────────────────────────
# BG — OLX.bg (override для priority)
# ─────────────────────────────────────────────────────────────


def build_bg() -> dict:
    olx_raw = load_json(RAW / "bg_olx.json")
    priority = load_json(OVERRIDES / "priority_bg.json")

    cities = []
    for o in olx_raw:
        name = o["city_name"]
        olx_id = o["city_id"]
        slug, is_priority = _priority_slug(name, priority, f"olx_bg_{olx_id}")
        cities.append(
            {
                "slug": slug,
                "name": name,
                "region": o.get("region_name", ""),
                "priority": is_priority,
                "refs": {"olx_bg": olx_id},
            }
        )

    cities = dedupe(cities)
    cities.sort(key=lambda c: (not c["priority"], c["name"]))
    print(f"  BG: {len(cities)} міст ({sum(1 for c in cities if c['priority'])} priority)")
    return {"country": "bg", "cities": cities}


# ─────────────────────────────────────────────────────────────
# DE — Kleinanzeigen
# ─────────────────────────────────────────────────────────────


def build_de() -> dict:
    raw = load_json(RAW / "de_kleinanzeigen.json")

    cities = []
    for o in raw:
        loc_id = o["location_id"]
        cities.append(
            {
                "slug": o.get("slug") or f"de_{loc_id}",
                "name": o["name"],
                "region": o.get("region", ""),
                "priority": o.get("priority", False),
                "refs": {"kleinanzeigen": loc_id},
            }
        )

    cities = dedupe(cities)
    cities.sort(key=lambda c: (not c["priority"], c["name"]))
    print(f"  DE: {len(cities)} міст ({sum(1 for c in cities if c['priority'])} priority)")
    return {"country": "de", "cities": cities}


# ─────────────────────────────────────────────────────────────
# ES — Habitaclia
# ─────────────────────────────────────────────────────────────


def build_es() -> dict:
    raw = load_json(RAW / "es_habitaclia.json")

    cities = []
    for o in raw:
        slug = o.get("slug") or f"es_{o['location_id']}"
        cities.append(
            {
                "slug": slug,
                "name": o["name"],
                "region": o.get("region", ""),
                "priority": o.get("priority", False),
                "refs": {"habitaclia": o["location_id"]},
            }
        )

    cities = dedupe(cities)
    cities.sort(key=lambda c: (not c["priority"], c["name"]))
    print(f"  ES: {len(cities)} міст ({sum(1 for c in cities if c['priority'])} priority)")
    return {"country": "es", "cities": cities}


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    print("Генерація каталогу:")
    builders = {
        "ua": build_ua,
        "pl": build_pl,
        "pt": build_pt,
        "ro": build_ro,
        "bg": build_bg,
        "de": build_de,
        "es": build_es,
    }

    total = 0
    for code, build_fn in builders.items():
        data = build_fn()
        total += len(data["cities"])
        save_json(OUT / f"{code}.json", data)

    print(f"\n✅ Всього: {total} міст у {len(builders)} країнах")
    print(f"✅ Записано в {OUT}")


if __name__ == "__main__":
    main()
