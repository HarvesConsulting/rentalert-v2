"""Тест StoriaParser: парсинг картки з HTML."""

from pathlib import Path

from rentalert.catalog.models import City, Source
from rentalert.parsers.storia import StoriaParser


def _make_source() -> Source:
    return Source(
        key="storia_ro",
        country="ro",
        name="Storia.ro",
        icon="🟣",
        kind="storia",
        base_url="https://www.storia.ro",
        enabled_by_default=True,
        categories=("apartment",),
        config={},
    )


def test_parse_card() -> None:
    html = Path("tests/fixtures/storia_card.html").read_text(encoding="utf-8")
    parser = StoriaParser(_make_source())
    city = City(
        slug="bucuresti",
        country="ro",
        name="Bucuresti",
        region="Bucuresti - Ilfov",
        priority=True,
        refs={"storia_ro": "bucuresti"},
    )
    listings = parser._parse_page(html, city.slug)
    assert len(listings) >= 1
    lst = listings[0]
    assert lst.source_key == "storia_ro"
    assert lst.id.startswith("storia_ro:")
    assert lst.link.startswith("https://www.storia.ro/ro/oferta/")


def test_no_slug_returns_empty() -> None:
    parser = StoriaParser(_make_source())
    city = City(
        slug="olx_ro_24693",
        country="ro",
        name="Abrud",
        region="Alba",
        priority=False,
        refs={"olx_ro": 24693},  # без storia_ro
    )
    assert parser.fetch(city, ["apartment"]) == []
