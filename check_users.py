from rentalert import config
from rentalert.db.client import TursoClient

c = TursoClient(config.TURSO_URL, config.TURSO_TOKEN)

# 1. Всі користувачі з підписками
rows = c.execute("SELECT chat_id, city_slug FROM user_cities ORDER BY chat_id")
print(f"Підписок: {len(rows)}")
print()

users: dict[str, list[str]] = {}
for r in rows:
    users.setdefault(str(r[0]), []).append(str(r[1]))

for chat_id, cities in users.items():
    # Дістаємо ім'я
    info = c.execute(
        "SELECT username, first_name, country, language, last_seen "
        "FROM user_settings WHERE chat_id = ?",
        [chat_id],
    )
    if info:
        username, first_name, country, lang, last_seen = info[0]
        name = first_name or "?"
        uname = f" (@{username})" if username else ""
        print(f"👤 {name}{uname}")
        print(f"   chat_id: {chat_id}")
        print(f"   country: {country}, lang: {lang}")
        print(f"   last_seen: {last_seen}")
        print(f"   міста: {', '.join(cities)}")
        print()
    else:
        print(f"👤 chat_id: {chat_id} (без профілю)")
        print(f"   міста: {', '.join(cities)}")
        print()
