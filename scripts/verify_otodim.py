"""Комплексна перевірка інтеграції Otodim перед пушем."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Додаємо src/ до path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

OK = "✅"
FAIL = "❌"
WARN = "⚠️ "

errors: list[str] = []
warnings: list[str] = []


def check(cond: bool, ok_msg: str, fail_msg: str) -> bool:
    if cond:
        print(f"{OK} {ok_msg}")
        return True
    print(f"{FAIL} {fail_msg}")
    errors.append(fail_msg)
    return False


print("=" * 70)
print("ПЕРЕВІРКА ІНТЕГРАЦІЇ OTODIM")
print("=" * 70)
print()

# ── 1. Файл парсера ──
print("─── 1. Файл парсера ───")
parser_file = ROOT / "src" / "rentalert" / "parsers" / "otodim.py"
check(parser_file.exists(), f"Файл {parser_file.name} існує", f"Немає {parser_file}")
print()

# ── 2. Імпорт парсера ──
print("─── 2. Імпорт OtodimParser ───")
try:
    from rentalert.parsers.otodim import OtodimParser, SOURCE_KEY
    check(True, f"Імпорт OK, SOURCE_KEY={SOURCE_KEY!r}", "")
except Exception as e:
    check(False, "", f"Помилка імпорту: {e}")
    sys.exit(1)
print()

# ── 3. registry.py ──
print("─── 3. Реєстрація в registry.py ───")
registry_text = (ROOT / "src" / "rentalert" / "parsers" / "registry.py").read_text(encoding="utf-8")
check(
    "from rentalert.parsers.otodim import OtodimParser" in registry_text,
    "Імпорт у registry.py знайдено",
    "Немає імпорту otodim у registry.py",
)
check(
    '"otodim": OtodimParser' in registry_text,
    'Запис "otodim": OtodimParser у словнику',
    'Немає "otodim": OtodimParser у словнику _PARSER_BY_KIND',
)
print()

# ── 4. sources.json ──
print("─── 4. sources.json ───")
sources = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
check(
    "otodim_ua" in sources,
    "otodim_ua у sources.json",
    "Немає otodim_ua у sources.json",
)
if "otodim_ua" in sources:
    src = sources["otodim_ua"]
    check(src.get("kind") == "otodim", f'kind="otodim"', f'kind неправильний: {src.get("kind")}')
    check(src.get("country") == "ua", f'country="ua"', f'country неправильний')
    check(src.get("base_url", "").startswith("https://"), f'base_url="{src.get("base_url")}"', "base_url неправильний")
print()

# ── 5. cities/ua.json ──
print("─── 5. cities/ua.json — refs з otodim_ua ───")
ua = json.loads((ROOT / "data" / "cities" / "ua.json").read_text(encoding="utf-8"))
cities_with_otodim = [c for c in ua["cities"] if "otodim_ua" in c.get("refs", {})]
check(
    len(cities_with_otodim) >= 20,
    f"Знайдено {len(cities_with_otodim)} міст з otodim_ua у refs",
    f"Замало міст: {len(cities_with_otodim)} (очікуємо 21)",
)

# Перевіряємо конкретні міста
required = ["kyiv", "lviv", "odesa", "kharkiv", "dnipro"]
missing = [s for s in required if not any(c["slug"] == s and "otodim_ua" in c["refs"] for c in ua["cities"])]
check(not missing, "Усі ключові міста мають otodim_ua", f"Немає otodim_ua у: {missing}")

for s in required:
    c = next((x for x in ua["cities"] if x["slug"] == s), None)
    if c:
        print(f"   {s:<12} → {c['refs'].get('otodim_ua')}")
print()

# ── 6. PARSER_REGISTRY ──
print("─── 6. PARSER_REGISTRY ───")
try:
    from rentalert.catalog.catalog import Catalog
    from rentalert.parsers.registry import build_registry, PARSER_REGISTRY

    cat = Catalog.load(ROOT / "data")
    build_registry(cat)

    check(
        "otodim_ua" in PARSER_REGISTRY,
        f"otodim_ua у PARSER_REGISTRY: {PARSER_REGISTRY['otodim_ua'].__class__.__name__}",
        "otodim_ua НЕ у PARSER_REGISTRY",
    )
    check(
        len(PARSER_REGISTRY) == 22,
        f"Всього парсерів: {len(PARSER_REGISTRY)}",
        f"Парсерів {len(PARSER_REGISTRY)}, очікуємо 22",
    )
    check(
        "storia_ro" in PARSER_REGISTRY,
        "storia_ro теж у реєстрі",
        "storia_ro НЕ у реєстрі",
    )
except Exception as e:
    check(False, "", f"Помилка build_registry: {e}")
print()

# ── 7. Функціональний тест парсера ──
print("─── 7. Функціональний тест (Київ) ───")
try:
    from rentalert.catalog.models import City, Source

    src_obj = Source(
        key="otodim_ua", country="ua", name="Otodim", icon="🏘",
        kind="otodim", base_url="https://otodim.com.ua",
        enabled_by_default=True, categories=("apartment",), config={},
    )
    city = City(
        slug="kyiv", country="ua", name="Київ", region="Київська область",
        priority=True, refs={"otodim_ua": "kyiv"},
    )

    parser = OtodimParser(src_obj)
    listings = parser.fetch(city, ["apartment"])

    check(
        len(listings) > 0,
        f"Парсер повернув {len(listings)} оголошень",
        f"Парсер повернув 0 оголошень",
    )

    if listings:
        first = listings[0]
        print()
        print("   Приклад першого оголошення:")
        print(f"   ID: {first.id}")
        print(f"   Ціна: {first.price}")
        print(f"   Кімнат: {first.rooms}")
        print(f"   Площа: {first.area_m2} м²")
        print(f"   Дата: {first.created_at}")
        print(f"   Локація: {first.location}")
        print(f"   URL: {first.link}")
        print(f"   Фото: {first.photo[:60]}...")

        # Валідація полів
        check(first.id.startswith("otodim_ua:"), f"ID має правильний префікс", f"ID без префіксу: {first.id}")
        check(first.link.startswith("https://otodim.com.ua/"), f"URL правильний", f"URL неправильний: {first.link}")
        check(" " in first.price or "—" in first.price, f"Ціна виглядає ОК", f"Ціна дивна: {first.price}")
        check(first.rooms in (None, "1", "2", "3", "4", "5", "6"), f"Кімнат: {first.rooms}", f"Кімнат дивне: {first.rooms}")
        check(first.created_at is not None, f"Дата є", f"Дата відсутня")
except Exception as e:
    import traceback
    check(False, "", f"Помилка: {e}")
    traceback.print_exc()
print()

# ── 8. Git status ──
print("─── 8. Git status ───")
import subprocess
try:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    if result.stdout.strip():
        print(result.stdout)
    else:
        print("   (немає змін)")
except Exception as e:
    print(f"{WARN} Не вдалось отримати git status: {e}")
print()

# ── Підсумок ──
print("=" * 70)
if errors:
    print(f"{FAIL} ЗНАЙДЕНО {len(errors)} ПОМИЛОК:")
    for e in errors:
        print(f"   • {e}")
    print()
    print("Виправ помилки і запусти перевірку ще раз.")
    sys.exit(1)
else:
    print(f"{OK} ВСІ ПЕРЕВІРКИ ПРОЙДЕНО!")
    print()
    print("Можна комітити і пушити.")
