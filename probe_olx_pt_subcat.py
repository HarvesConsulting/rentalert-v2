"""Знайти ID підкатегорії оренди в OLX.pt."""

from curl_cffi import requests as cffi_requests

url = "https://www.olx.pt/api/v1/offers/"
session = cffi_requests.Session(impersonate="chrome")

# Спроба 1: різні ID поруч з 16
print("=== ID поруч з 16 ===")
for cat_id in [16, 17, 15, 18, 19, 20, 21, 22, 23, 24, 25]:
    r = session.get(
        url,
        params={
            "offset": 0,
            "limit": 3,
            "category_id": cat_id,
            "region_id": 11,
            "sort_by": "created_at:desc",
        },
        timeout=15,
    )

    if r.status_code == 200:
        items = r.json().get("data", []) or []
        titles = [it.get("title", "")[:60] for it in items[:3]]
        text = " ".join(titles).lower()
        is_imovel = any(
            k in text
            for k in [
                "apartament",
                "arrendament",
                "alugar",
                "quarto",
                "casa",
                "imóvel",
                "t1",
                "t2",
                "t3",
                "armazém",
            ]
        )
        marker = "🏠" if is_imovel else "  "
        print(f"{marker} cat={cat_id}: {len(items)} items")
        for t in titles:
            print(f"      {t}")
    else:
        print(f"   cat={cat_id}: HTTP {r.status_code}")

print()

# Спроба 2: ID 10000-10100 (підкатегорії зазвичай тут)
print("=== ID в діапазоні 10000-10100 ===")
found = []
for cat_id in range(10000, 10100):
    r = session.get(
        url,
        params={
            "offset": 0,
            "limit": 1,
            "category_id": cat_id,
            "region_id": 11,
        },
        timeout=10,
    )
    if r.status_code == 200:
        items = r.json().get("data", []) or []
        if items:
            title = items[0].get("title", "")[:60]
            text = title.lower()
            is_imovel = any(
                k in text
                for k in ["apartament", "arrendament", "alugar", "quarto", "casa", "imóvel"]
            )
            marker = "🏠" if is_imovel else "  "
            print(f"{marker} cat={cat_id}: {title}")
            if is_imovel:
                found.append(cat_id)

print()
print(f"Знайдено IMOBILIARIO: {found}")
