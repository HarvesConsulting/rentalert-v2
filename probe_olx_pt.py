"""Тимчасово: знайти правильні category_id для OLX.pt."""

import re

from curl_cffi import requests as cffi_requests

# Сторінка оренди квартир
url = "https://www.olx.pt/imoveis/apartamento-casa-a-venda/apartamentos-arrenda/portosanto/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

session = cffi_requests.Session(impersonate="chrome")
r = session.get(url, headers=headers, timeout=30)

print(f"Status: {r.status_code}")
print(f"Size: {len(r.text)}")
print(f"URL: {r.url}")
print()

if r.status_code != 200:
    print("Response (first 500):")
    print(r.text[:500])
    raise SystemExit(1)

html = r.text

# Шукаємо category_id різними способами
print("=== Пошук category_id / categoryId ===")

# 1. "category_id":1234
for m in re.finditer(r'"category_?[Ii]d"\s*:\s*(\d+)', html):
    print(f"  category_id = {m.group(1)}")

# 2. "category":{"id":1234
for m in re.finditer(r'"category"\s*:\s*\{[^}]{0,200}?"id"\s*:\s*(\d+)', html):
    print(f"  category.id = {m.group(1)}")

# 3. region_id
print()
print("=== Пошук region_id ===")
for m in re.finditer(r'"region_?[Ii]d"\s*:\s*(\d+)', html):
    print(f"  region_id = {m.group(1)}")

# 4. Шукаємо "id":число поруч з "name":"Apartamentos"
print()
print("=== Пошук 'Apartamentos' / 'Arrendamento' з ID ===")
for m in re.finditer(
    r'\{[^{}]{0,300}?"name"\s*:\s*"(Apartamentos|Arrendamento)"[^{}]{0,300}?\}', html
):
    snippet = m.group(0)
    print(f"  {snippet[:300]}")
    print()

# 5. Витягуємо __NEXT_DATA__ (якщо є)
print()
print("=== __NEXT_DATA__ / __INITIAL_STATE__ ===")
next_match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if next_match:
    print(f"  Знайдено __NEXT_DATA__, довжина: {len(next_match.group(1))}")
    # Шукаємо в ньому category_id
    nd = next_match.group(1)
    for m in re.finditer(r'"categoryI?d?"\s*:\s*(\d+)', nd):
        print(f"    category = {m.group(1)}")
    for m in re.finditer(r'"regionI?d?"\s*:\s*(\d+)', nd):
        print(f"    region = {m.group(1)}")
else:
    print("  Не знайдено __NEXT_DATA__")

# 6. Просто всі "id":число
print()
print("=== Усі унікальні ID (перші 20) ===")
all_ids = set()
for m in re.finditer(r'"id"\s*:\s*(\d+)', html):
    all_ids.add(int(m.group(1)))

sorted_ids = sorted(all_ids)[:20]
for i in sorted_ids:
    print(f"  id = {i}")
