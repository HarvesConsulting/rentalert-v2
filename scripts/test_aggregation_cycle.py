"""Тест run_aggregation_cycle — пошук нових оголошень."""

from pathlib import Path

from rentalert import config
from rentalert.catalog.catalog import Catalog
from rentalert.db.client import TursoClient
from rentalert.db import queries as db
from rentalert.parsers.registry import build_registry
from rentalert.services.aggregator import run_aggregation_cycle


def main() -> None:
    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)
    catalog = Catalog.load(Path("data"))
    build_registry(catalog)

    subs = db.get_all_user_cities(client)
    print(f"📊 Підписок у БД: {len(subs)}")
    if subs:
        for chat_id, cities in list(subs.items())[:3]:
            print(f"   chat_id={chat_id}: {cities}")
    print()

    notified = []

    def notify_fn(chat_id: str, city_slug: str, listings: list) -> None:
        notified.append((chat_id, city_slug, len(listings)))
        print(f"   📬 notify: chat={chat_id}, city={city_slug}, listings={len(listings)}")

    print("🔍 run_aggregation_cycle...")
    stats = run_aggregation_cycle(
        catalog=catalog,
        client=client,
        notify_fn=notify_fn,
        recent_hours=24,
    )
    print()
    print(f"✅ Статистика:")
    print(f"   pairs_checked:    {stats.pairs_checked}")
    print(f"   listings_fetched: {stats.listings_fetched}")
    print(f"   listings_new:     {stats.listings_new}")
    print(f"   users_notified:   {stats.users_notified}")
    print(f"   errors:           {stats.errors}")


if __name__ == "__main__":
    main()
