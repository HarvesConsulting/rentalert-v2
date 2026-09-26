"""Тимчасово: перевірити notifier."""

from rentalert.services.notifier import TelegramNotifier

n = TelegramNotifier("fake:token")

methods = [m for m in dir(n) if not m.startswith("_")]
print("OK — методи:")
for m in sorted(methods):
    print(f"  - {m}")
