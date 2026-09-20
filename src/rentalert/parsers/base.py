"""Базовий клас парсера + dataclass Listing.

Усі парсери успадковують Parser і повертають список Listing.
Listing — уніфікований формат, незалежний від джерела.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rentalert.catalog.models import City, Source


# ─────────────────────────────────────────────────────────────
# Listing — уніфіковане оголошення
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Listing:
    """Оголошення, нормалізоване з будь-якого джерела.

    Приклад:
        Listing(
            id="olx_ua:12345",
            source_key="olx_ua",
            city_slug="kyiv",
            title="2-кімнатна квартира, Печерськ",
            price="15 000 грн",
            location="Київ, Печерський",
            link="https://www.olx.ua/d/obyavlenie/...",
            photo="https://.../photo.jpg",
            rooms="2",
            category="apartment",
            category_icon="🏢",
            category_label="Квартири",
            created_at=datetime(2026, 9, 20, 10, 30, tzinfo=UTC),
            raw={...},
        )
    """

    id: str
    """Глобально унікальний: f"{source_key}:{external_id}"."""

    source_key: str
    """Ключ джерела: 'olx_ua', 'dimria', 'kleinanzeigen'."""

    city_slug: str
    """Slug міста з каталогу: 'kyiv', 'lviv'."""

    title: str
    """Заголовок оголошення."""

    price: str
    """Ціна як рядок: '15 000 грн', '€1200', '—'."""

    location: str
    """Локація як рядок: 'Київ, Печерський'."""

    link: str
    """Повний URL оголошення."""

    photo: str
    """URL першого фото (порожній рядок, якщо немає)."""

    rooms: str | None
    """Кількість кімнат як рядок ('2') або None."""

    category: str
    """Ключ категорії: 'apartment', 'house', 'room', 'daily'."""

    category_icon: str
    """Емодзі категорії: '🏢', '🏠'."""

    category_label: str
    """Локалізована назва: 'Квартири', 'Mieszkania'."""

    created_at: datetime | None
    """Час публікації (UTC) або None, якщо невідомо."""

    raw: dict[str, Any] = field(default_factory=dict)
    """Оригінальні дані з джерела (для дебагу, не для UI)."""

    def is_fresh(self, max_age_hours: int = 6) -> bool:
        """Чи оголошення свіже (молодше за max_age_hours)."""
        if self.created_at is None:
            return True  # якщо невідомо — вважаємо свіжим
        from datetime import UTC, datetime as dt
        now = dt.now(UTC)
        delta = now - self.created_at
        return delta.total_seconds() < max_age_hours * 3600


# ─────────────────────────────────────────────────────────────
# Parser — базовий клас
# ─────────────────────────────────────────────────────────────

class Parser(ABC):
    """Абстрактний парсер одного джерела.

    Приклад:
        class OLXParser(Parser):
            def fetch(self, city: City, categories: list[str]) -> list[Listing]:
                ...
    """

    def __init__(self, source: Source) -> None:
        self.source = source

    @abstractmethod
    def fetch(self, city: City, categories: list[str]) -> list[Listing]:
        """Повертає оголошення для міста й категорій.

        Args:
            city: об'єкт City з каталогу
            categories: список ключів категорій ('apartment', 'house', ...)

        Returns:
            Список Listing. Порожній список, якщо нічого не знайдено.
        """

    # ─────────────────────────────────────────────────────
    # Допоміжні методи
    # ─────────────────────────────────────────────────────

    def supports_category(self, category: str) -> bool:
        """Чи підтримує це джерело вказану категорію."""
        return category in self.source.categories

    def filter_categories(self, categories: list[str]) -> list[str]:
        """Фільтрує категорії, залишаючи тільки підтримувані джерелом."""
        return [c for c in categories if self.supports_category(c)]

    def external_id(self, city: City) -> Any | None:
        """ID міста в цьому джерелі (з city.refs)."""
        return city.external_id(self.source.key)

    def make_id(self, external_id: int | str) -> str:
        """Формує глобально унікальний ID оголошення."""
        return f"{self.source.key}:{external_id}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.source.key!r})"
