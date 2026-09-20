"""Dataclass-моделі каталогу: Country, Source, City.

Каталог immutable — після завантаження ніщо його не змінює.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Country:
    """Країна, у якій працює бот.

    Приклад:
        Country(
            code="ua",
            name="🇺🇦 Україна",
            name_en="Ukraine",
            language="uk",
            currency="грн",
            free=True,
            price_stars=0,
        )
    """

    code: str
    """Код країни: 'ua', 'pl', 'pt', 'ro', 'bg', 'de', 'es'."""

    name: str
    """Назва з емодзі: '🇺🇦 Україна'."""

    name_en: str
    """Назва англійською: 'Ukraine'."""

    language: str
    """Мова інтерфейсу за замовчуванням: 'uk', 'pl', 'pt', ..."""

    currency: str
    """Символ валюти: 'грн', 'zł', '€', 'lei', 'лв'."""

    free: bool
    """Чи безкоштовна країна."""

    price_stars: int
    """Ціна в Telegram Stars на місяць (0 для безкоштовних)."""


@dataclass(frozen=True, slots=True)
class Source:
    """Джерело оголошень.

    Приклад:
        Source(
            key="olx_ua",
            country="ua",
            name="OLX.ua",
            icon="🟢",
            kind="olx",
            base_url="https://www.olx.ua",
            enabled_by_default=True,
            categories=("apartment", "house", "room", "daily"),
            config={"category_ids": {"apartment": 1760, "house": 330, ...}},
        )
    """

    key: str
    """Унікальний ключ: 'olx_ua', 'dimria', 'kleinanzeigen'."""

    country: str
    """Код країни, до якої належить джерело."""

    name: str
    """Назва для UI: 'OLX.ua', 'DIM.RIA'."""

    icon: str
    """Емодзі для UI: '🟢', '🏘'."""

    kind: str
    """Тип парсера: 'olx', 'dimria', 'kleinanzeigen', 'habitaclia'."""

    base_url: str
    """Базовий URL сайту."""

    enabled_by_default: bool
    """Чи увімкнено джерело за замовчуванням у налаштуваннях."""

    categories: tuple[str, ...]
    """Категорії, які підтримує джерело: ('apartment', 'house', ...)."""

    config: dict[str, Any]
    """Специфічні налаштування (ID категорій, слаги, API-база)."""


@dataclass(frozen=True, slots=True)
class City:
    """Місто або регіон.

    Приклад:
        City(
            slug="kyiv",
            country="ua",
            name="Київ",
            region="Київська область",
            priority=True,
            refs={"olx_ua": 268, "dimria": 10},
        )
    """

    slug: str
    """Унікальний slug у межах країни: 'kyiv', 'lviv', 'dimria_12800'."""

    country: str
    """Код країни: 'ua', 'pl', ..."""

    name: str
    """Назва: 'Київ', 'Warszawa'."""

    region: str
    """Регіон/область: 'Київська область', '' (порожньо, якщо немає)."""

    priority: bool
    """Пріоритетне місто (показується вище в пошуку)."""

    refs: dict[str, Any]
    """ID міста в кожному джерелі: {'olx_ua': 268, 'dimria': 10}."""

    def external_id(self, source_key: str) -> Any | None:
        """Повертає ID міста в конкретному джерелі або None."""
        return self.refs.get(source_key)

    def supports(self, source_key: str) -> bool:
        """Чи підтримує це місто вказане джерело."""
        return source_key in self.refs

    def source_keys(self) -> tuple[str, ...]:
        """Усі джерела, які підтримують це місто."""
        return tuple(self.refs.keys())
