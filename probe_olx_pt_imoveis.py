"""Перебір category_id для нерухомості OLX.pt."""

from curl_cffi import requests as cffi_requests

url = "https://www.olx.pt/api/v1/offers/"

# Можливі ID нерухомості (з різних джерел)
# 300-400 — часто категорії, 1000-9999 — підкатегорії
candidate_ids = [
    16,  # ваш поточний (не працює)
    100,
    200,
    300,
    400,
    500,
    600,
    700,
    800,
    900,
    1000,
    1001,
    1010,
    1100,
    1200,
    1300,
    1400,
    1500,
    2000,
    3000,
    4000,
    5000,
    6000,
    7000,
    8000,
    9000,
    # OLX.pl IDs (може, схожі):
    15,
    18,
    # OLX.ro / olx.bg IDs:
    909,
    913,
    536,
    541,
]

# region_id для Португалії (спробуємо кілька)
region_id = 11  # працює, але це не Porto — шукаємо по всій країні

session = cffi_requests.Session(impersonate="chrome")

for cat_id in candidate_ids:
    params = {
        "offset": 0,
        "limit": 3,
        "category_id": cat_id,
        "region_id": region_id,
        "sort_by": "created_at:desc",
    }
    try:
        r = session.get(url, params=params, timeout=15)
    except Exception as e:
        print(f"cat={cat_id}: ERROR {e}")
        continue

    if r.status_code == 200:
        data = r.json()
        items = data.get("data", []) or []
        if not items:
            continue
        titles = [it.get("title", "")[:60] for it in items[:3]]
        # Шукаємо тільки ті, де є "apartamento", "arrendamento", "quarto", "casa"
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
                "imovel",
                "t1",
                "t2",
                "t3",
            ]
        )
        marker = "🏠 IMOBILIARIO" if is_imovel else ""
        print(f"cat={cat_id}: {len(items)} items {marker}")
        for t in titles:
            print(f"   - {t}")
    elif r.status_code == 400:
        # Невалідний ID — пропускаємо (щоб не спамити)
        continue
    else:
        print(f"cat={cat_id}: HTTP {r.status_code}")

print("\nГотово.")
