"""Перевірка імпорту Parser999Md."""

try:
    from rentalert.parsers.md999 import Parser999Md
    print("✅ Parser999Md імпортовано")

    methods = [
        m for m in dir(Parser999Md)
        if m.startswith("_") and not m.startswith("__")
    ]
    print(f"\nМетоди класу:")
    for m in sorted(methods):
        print(f"  {m}")

    # Перевіряємо, що критичні методи всередині класу
    critical = ["_fetch_advert", "_parse_advert", "_post", "_gql_search"]
    print(f"\nКритичні методи:")
    for name in critical:
        status = "✅" if hasattr(Parser999Md, name) else "❌"
        print(f"  {status} {name}")

except Exception as e:
    import traceback
    print(f"❌ Помилка імпорту: {e}")
    traceback.print_exc()
