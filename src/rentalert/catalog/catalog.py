"""Клас Catalog — центральна точка доступу до довідника.

Каталог immutable: після завантаження ніщо його не змінює.
Усі пошуки — через методи Catalog.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from rentalert.catalog.loader import load_cities_dir, load_countries, load_sources
from rentalert.catalog.models import City, Country, Source


def _normalize(text: str | None) -> str:
    """Нормалізація для пошуку: lower + видалення діакритики."""
    if not text:
        return ""
    s = str(text).lower().strip()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


# ─────────────────────────────────────────────────────────────
# Транслітерація: кирилиця ↔ латиниця
# ─────────────────────────────────────────────────────────────

_UA_TO_LATIN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g",
    "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z",
    "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ь": "", "ю": "iu", "я": "ia",
    # російські, які часто трапляються
    "ы": "y", "э": "e", "ё": "e", "ъ": "",
}

_LATIN_TO_UA: dict[str, str] = {
    "a": "а", "b": "б", "v": "в", "h": "г", "g": "ґ",
    "d": "д", "e": "е", "z": "з", "y": "и", "i": "і",
    "k": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "r": "р", "s": "с", "t": "т", "u": "у",
    "f": "ф", "c": "ц", "j": "й", "w": "в",
}


def _translit_to_latin(text: str) -> str:
    """Кирилиця → латиниця (для пошуку в латиномовних каталогах)."""
    if not text:
        return ""
    s = _normalize(text)
    result: list[str] = []
    for ch in s:
        if ch in _UA_TO_LATIN:
            result.append(_UA_TO_LATIN[ch])
        else:
            result.append(ch)
    return "".join(result)


def _translit_to_cyrillic(text: str) -> str:
    """Латиниця → кирилиця (для пошуку в кириличних каталогах)."""
    if not text:
        return ""
    s = _normalize(text)
    result: list[str] = []
    for ch in s:
        if ch in _LATIN_TO_UA:
            result.append(_LATIN_TO_UA[ch])
        else:
            result.append(ch)
    return "".join(result)


class Catalog:
    """Immutable довідник країн, джерел, міст."""

    def __init__(
        self,
        countries: dict[str, Country],
        sources: dict[str, Source],
        cities: dict[str, City],
    ) -> None:
        self._countries = countries
        self._sources = sources
        self._cities = cities

        self._cities_by_country: dict[str, list[City]] = {}
        self._sources_by_country: dict[str, list[Source]] = {}
        self._index_by_ext_id: dict[tuple[str, str], City] = {}

        for city in cities.values():
            self._cities_by_country.setdefault(city.country, []).append(city)
            for source_key, ext_id in city.refs.items():
                self._index_by_ext_id[(source_key, str(ext_id))] = city

        for source in sources.values():
            self._sources_by_country.setdefault(source.country, []).append(source)

    @classmethod
    def load(cls, data_dir: Path) -> Catalog:
        """Завантажує весь каталог з data/."""
        countries = load_countries(data_dir / "countries.json")
        sources = load_sources(data_dir / "sources.json")
        cities = load_cities_dir(data_dir / "cities")
        return cls(countries, sources, cities)

    # ─── Прямий доступ ───

    def country(self, code: str) -> Country | None:
        return self._countries.get(code)

    def source(self, key: str) -> Source | None:
        return self._sources.get(key)

    def city(self, slug: str) -> City | None:
        return self._cities.get(slug)

    # ─── Колекції ───

    def all_countries(self) -> list[Country]:
        return list(self._countries.values())

    def all_sources(self) -> list[Source]:
        return list(self._sources.values())

    def all_cities(self) -> list[City]:
        return list(self._cities.values())

    def cities_of(self, country: str) -> list[City]:
        return list(self._cities_by_country.get(country, []))

    def sources_of(self, country: str) -> list[Source]:
        return list(self._sources_by_country.get(country, []))

    # ─── Зворотний пошук ───

    def find_city_by_external_id(self, source_key: str, ext_id: int | str) -> City | None:
        return self._index_by_ext_id.get((source_key, str(ext_id)))

    # ─── Пошук міст ───

    def find_cities(
        self,
        query: str,
        country: str,
        limit: int = 8,
    ) -> list[City]:
        if not query or len(query) < 2:
            return []

        candidates = self._cities_by_country.get(country, [])
        if not candidates:
            return []

        # 1. Точний пошук
        result = self._search_exact(query, candidates, limit)
        if len(result) >= limit:
            return result[:limit]

        seen: set[str] = {c.slug for c in result}

        # 2. Транслітерація: кирилиця → латиниця
        translit_lat = _translit_to_latin(query)
        if translit_lat != _normalize(query):
            for c in self._search_exact(translit_lat, candidates, limit):
                if c.slug not in seen:
                    result.append(c)
                    seen.add(c.slug)

        if len(result) >= limit:
            return result[:limit]

        # 3. Транслітерація: латиниця → кирилиця
        translit_cyr = _translit_to_cyrillic(query)
        if translit_cyr != _normalize(query):
            for c in self._search_exact(translit_cyr, candidates, limit):
                if c.slug not in seen:
                    result.append(c)
                    seen.add(c.slug)

        if len(result) >= limit:
            return result[:limit]

        # 4. Fuzzy на оригіналі
        for c in self._search_fuzzy(query, candidates, limit - len(result)):
            if c.slug not in seen:
                result.append(c)
                seen.add(c.slug)

        if len(result) >= limit:
            return result[:limit]

        # 5. Fuzzy на трансліті (латиниця)
        for c in self._search_fuzzy(translit_lat, candidates, limit - len(result)):
            if c.slug not in seen:
                result.append(c)
                seen.add(c.slug)

        return result[:limit]

    def _search_exact(
        self,
        query: str,
        candidates: list[City],
        limit: int,
    ) -> list[City]:
        """Точний пошук: exact → startswith → contains."""
        q = _normalize(query)
        if not q:
            return []

        exact: list[City] = []
        starts: list[City] = []
        contains: list[City] = []

        for city in candidates:
            n = _normalize(city.name)
            if n == q:
                exact.append(city)
            elif n.startswith(q):
                starts.append(city)
            elif q in n:
                contains.append(city)

        def sort_key(c: City) -> tuple[int, str]:
            return (not c.priority, c.name)

        exact.sort(key=sort_key)
        starts.sort(key=sort_key)
        contains.sort(key=sort_key)

        return (exact + starts + contains)[:limit]

    def _search_fuzzy(
        self,
        query: str,
        candidates: list[City],
        limit: int,
    ) -> list[City]:
        """Fuzzy-пошук через difflib."""
        from difflib import get_close_matches

        q = _normalize(query)
        if not q or limit <= 0:
            return []

        name_map: dict[str, City] = {}
        for city in candidates:
            n = _normalize(city.name)
            if n and n not in name_map:
                name_map[n] = city

        matches = get_close_matches(
            q, list(name_map.keys()), n=limit, cutoff=0.75,
        )
        return [name_map[m] for m in matches]

    # ─── Джерела для міста ───

    def sources_for_city(self, city_slug: str) -> list[Source]:
        city = self._cities.get(city_slug)
        if not city:
            return []
        result: list[Source] = []
        for key in city.refs:
            source = self._sources.get(key)
            if source:
                result.append(source)
        return result

    # ─── Службове ───

    def stats(self) -> dict[str, int]:
        return {
            "countries": len(self._countries),
            "sources": len(self._sources),
            "cities": len(self._cities),
        }

    def __repr__(self) -> str:
        s = self.stats()
        return f"Catalog(countries={s['countries']}, sources={s['sources']}, cities={s['cities']})"
