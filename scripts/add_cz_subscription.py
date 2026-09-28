"""Додає чеське місто (brno) в підписку для тестування циклу."""

from rentalert import config
from rentalert.db.client import TursoClient
from rentalert.db import queries as db


def main() -> None:
    client = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

    # Беремо chat_id з наявної підписки
    subs = db.get_all_user_cities(client)
    if not subs:
        print("❌ Немає підписок — не можемо визначити chat_id")
        return

    chat_id = list(subs.keys())[0]
    print(f"📝 chat_id: {chat_id}")
    print(f"   Поточні міста: {subs[chat_id]}")

    # Додаємо brno
    db.add_user_city(client, chat_id, "brno")
    print(f"\n✅ Додано 'brno'")

    # Перевіряємо
    new_cities = db.get_user_cities(client, chat_id)
    print(f"📋 Оновлені міста: {new_cities}")


if __name__ == "__main__":
    main()
