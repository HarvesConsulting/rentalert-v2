"""Завантаження JSON-файлів каталогу в dataclass-об'єкти.

Функції чисті: отримують шлях, повертають словник об'єктів.
Ніякого глобального стану.
"""

from __future__ import annotations

import json
from pathlib import Path

from rentalert.catalog.models import City, Country, Source

# ─────────────────────────────────────────────────────────────
# Завантаження країн
# ─────────────────────────────────────────────────────────────

def load_countries(path: Path) -> dict[str, Country]:
    """Читає countries.json → dict[code, Country]."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    result: dict[str, Country] = {}
    for code, data in raw.items():
        result[code] = Country(
            code=data["code"],
            name=data["name"],
            name_en=data["name_en"],
            language=data["language"],
            currency=data["currency"],
            free=bool(data["free"]),
            price_stars=int(data["price_stars"]),
        )
    return result


# ─────────────────────────────────────────────────────────────
# Завантаження джерел
# ─────────────────────────────────────────────────────────────

def load_sources(path: Path) -> dict[str, Source]:
    """Читає sources.json → dict[key, Source]."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    result: dict[str, Source] = {}
    for key, data in raw.items():
        result[key] = Source(
            key=data["key"],
            country=data["country"],
            name=data["name"],
            icon=data["icon"],
            kind=data["kind"],
            base_url=data["base_url"],
            enabled_by_default=bool(data["enabled_by_default"]),
            categories=tuple(data["categories"]),
            config=dict(data.get("config", {})),
        )
    return result


# ─────────────────────────────────────────────────────────────
# Завантаження міст
# ─────────────────────────────────────────────────────────────

def load_cities_dir(path: Path) -> dict[str, City]:
    """Читає всі data/cities/*.json → dict[slug, City].

    Кидає ValueError, якщо знайдено дублікат slug (у межах усіх країн).
    """
    result: dict[str, City] = {}

    for file in sorted(path.glob("*.json")):
        with open(file, encoding="utf-8") as f:
            data = json.load(f)

        country = data["country"]
        for c in data["cities"]:
            slug = c["slug"]
            if slug in result:
                raise ValueError(
                    f"Duplicate city slug {slug!r}: "
                    f"already in {result[slug].country}, "
                    f"found again in {country} ({file.name})"
                )
            result[slug] = City(
                slug=slug,
                country=country,
                name=c["name"],
                region=c.get("region", ""),
                priority=bool(c.get("priority", False)),
                refs=dict(c.get("refs", {})),
            )

    return result
