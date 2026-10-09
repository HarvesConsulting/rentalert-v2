"""Швидка перевірка, що Playwright працює.

Запуск:
    python scripts/check_playwright.py
"""

from playwright.sync_api import sync_playwright

print("Запускаю Playwright...")

with sync_playwright() as p:
    print("  ✅ Playwright запущено")

    browser = p.chromium.launch(headless=True)
    print("  ✅ Браузер запущено")

    page = browser.new_page()
    page.goto("https://example.com", wait_until="domcontentloaded", timeout=15000)
    title = page.title()
    print(f"  ✅ Сторінка завантажена: {title}")

    browser.close()
    print("  ✅ Браузер закрито")

print()
print("🎉 Playwright працює!")
