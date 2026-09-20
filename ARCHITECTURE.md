# ARCHITECTURE.md

RentAlert v2 — агрегатор оренди житла.

---

## 1. Призначення

Telegram-бот, який відстежує **нові оголошення про оренду житла** на кількох сайтах і надсилає їх користувачам.

**Ключова відмінність від v1:** одне місто може мати **кілька джерел** (OLX, DIM.RIA, Rieltor, …), і користувач обирає, з яких саме джерел отримувати оголошення.

---

## 2. Доменна модель

```
Country  1──N  Source
Country  1──N  City
City     N──N  Source         (через City.refs)

User     1──N  UserCity       (підписка на місто)
User     1──N  UserSource     (увімкнені джерела)
Listing  N──1  Source         (з якого джерела)
Listing  N──1  City           (нормалізоване місто)
```

### Сутності

| Сутність | Опис | Приклад |
|----------|------|---------|
| `Country` | Країна | `ua`, `pl`, `de` |
| `Source` | Джерело оголошень | `olx_ua`, `dimria`, `kleinanzeigen` |
| `City` | Місто/регіон | `kyiv`, `lviv`, `es_madrid` |
| `CityRef` | ID міста в конкретному джерелі | `(kyiv, olx_ua) → 121` |
| `Listing` | Оголошення | нормалізоване |
| `User` | Користувач Telegram | `chat_id` |

---

## 3. Каталог (immutable)

Весь довідник завантажується **один раз при старті** з JSON-файлів у пам'ять.

```
data/
├── countries.json
├── sources.json
└── cities/
    ├── ua.json
    ├── pl.json
    ├── pt.json
    ├── ro.json
    ├── bg.json
    ├── de.json
    └── es.json
```

### `data/countries.json`

```json
{
  "ua": {
    "code": "ua",
    "name": "🇺🇦 Україна",
    "name_en": "Ukraine",
    "language": "uk",
    "currency": "грн",
    "free": true,
    "price_stars": 0
  }
}
```

### `data/sources.json`

```json
{
  "olx_ua": {
    "key": "olx_ua",
    "country": "ua",
    "name": "OLX.ua",
    "icon": "🟢",
    "kind": "olx",
    "base_url": "https://www.olx.ua",
    "enabled_by_default": true,
    "categories": ["apartment", "house", "room", "daily"],
    "config": {
      "category_ids": {
        "apartment": 1760,
        "house": 330,
        "room": 1756,
        "daily": 3709
      }
    }
  }
}
```

### `data/cities/ua.json`

```json
{
  "country": "ua",
  "cities": [
    {
      "slug": "kyiv",
      "name": "Київ",
      "region": "Київська область",
      "priority": true,
      "refs": {
        "olx_ua": 121,
        "dimria": 140
      }
    }
  ]
}
```

**Правила:**
- `slug` унікальний **у межах країни**
- `refs` містить **тільки ті джерела, які підтримують це місто**
- `region` може бути порожнім
- `priority` — для сортування в пошуку

---

## 4. Модулі

```
src/rentalert/
├── __init__.py
├── __main__.py              # python -m renalert
├── app.py                   # Flask application factory
├── config.py                # env
├── catalog/
│   ├── models.py            # dataclass: Country, Source, City
│   ├── loader.py            # JSON → об'єкти
│   └── catalog.py           # клас Catalog
├── parsers/
│   ├── base.py              # Parser(ABC), Listing
│   ├── registry.py          # SOURCE_KEY → Parser
│   ├── olx.py
│   ├── dimria.py
│   ├── kleinanzeigen.py
│   └── habitaclia.py
├── db/
│   ├── client.py            # Turso HTTP client
│   ├── schema.py            # CREATE TABLE + міграції
│   └── queries.py           # високорівневі запити
├── services/
│   ├── aggregator.py        # головний цикл
│   ├── notifier.py          # Telegram
│   └── user.py              # налаштування користувача
└── bot/
    ├── handlers.py          # update → дія
    ├── callbacks.py         # inline-кнопки
    ├── keyboards.py         # клавіатури
    ├── states.py            # FSM
    └── ui_texts.py          # локалізовані тексти
```

---

## 5. Ключові класи

### `catalog.models`

```python
@dataclass(frozen=True)
class Country:
    code: str
    name: str
    name_en: str
    language: str
    currency: str
    free: bool
    price_stars: int

@dataclass(frozen=True)
class Source:
    key: str
    country: str
    name: str
    icon: str
    kind: str                       # 'olx' | 'dimria' | 'kleinanzeigen' | 'habitaclia'
    base_url: str
    enabled_by_default: bool
    categories: tuple[str, ...]
    config: dict

@dataclass(frozen=True)
class City:
    slug: str
    country: str
    name: str
    region: str
    priority: bool
    refs: dict[str, Any]            # {source_key: external_id}

    def external_id(self, source_key: str) -> Any | None:
        return self.refs.get(source_key)
```

### `parsers.base`

```python
@dataclass
class Listing:
    id: str                         # глобально унікальний: f"{source_key}:{external_id}"
    source_key: str
    city_slug: str
    title: str
    price: str
    location: str
    link: str
    photo: str
    rooms: str | None
    category: str
    category_icon: str
    category_label: str
    created_at: datetime | None
    raw: dict

class Parser(ABC):
    def __init__(self, source: Source):
        self.source = source

    @abstractmethod
    def fetch(self, city: City, categories: list[str]) -> list[Listing]: ...
```

---

## 6. Схема БД

```sql
CREATE TABLE seen_listings (
    id TEXT PRIMARY KEY,              -- f"{source_key}:{external_id}"
    source_key TEXT NOT NULL,
    city_slug TEXT NOT NULL,
    title TEXT, price TEXT, location TEXT, link TEXT,
    rooms TEXT, category TEXT, photo TEXT,
    category_icon TEXT, category_label TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    first_seen DATETIME
);

CREATE TABLE user_cities (
    chat_id TEXT NOT NULL,
    city_slug TEXT NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, city_slug)
);

CREATE TABLE user_sources (
    chat_id TEXT NOT NULL,
    source_key TEXT NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, source_key)
);

CREATE TABLE user_settings (...);
CREATE TABLE user_favorites (...);
CREATE TABLE user_activity (...);
```

---

## 7. Потік даних

### Старт застосунку

```
1. init_db()                 — створення таблиць, міграції
2. Catalog.load()            — JSON → пам'ять
3. build_registry(catalog)   — реєстрація парсерів
4. scheduler.start()         — APScheduler
5. webhook                   — Telegram
```

### Цикл агрегатора (кожні 2 хв)

```python
def run_aggregation_cycle():
    subscriptions = db.get_all_subscriptions()

    pairs = set()
    for sub in subscriptions:
        for sk in sub.source_keys:
            pairs.add((sub.city_slug, sk))

    fresh = {}
    for city_slug, source_key in pairs:
        city = catalog.city(city_slug)
        parser = PARSER_REGISTRY[source_key]
        listings = parser.fetch(city, categories)
        new = _filter_and_save(listings)
        if new:
            fresh[(city_slug, source_key)] = new

    for sub in subscriptions:
        to_send = []
        for sk in sub.source_keys:
            to_send.extend(fresh.get((sub.city_slug, sk), []))
        if to_send:
            notifier.send(sub.chat_id, sub.city_slug, to_send)
```

**Один цикл. Одна логіка. Жодних окремих циклів для DIM.RIA.**

---

## 8. Тести

- `tests/catalog/` — завантаження JSON, пошук міст
- `tests/parsers/` — парсери з фікстурами (JSON/HTML-відповіді)
- `tests/services/` — агрегатор, дедуплікація

Фікстури — у `tests/fixtures/`.

---

## 9. CI

`.github/workflows/tests.yml`:
- Python 3.11 + 3.12
- `ruff check` → `ruff format --check` → `mypy` → `pytest`

---

## 10. План реалізації

| Етап | Що робимо | Критерій готовності |
|------|-----------|---------------------|
| **0** | Каркас пакета | `pip install -e .[dev]` працює |
| **1** | Каталог + UA + `olx_ua` | `Catalog.load()` + тести |
| **2** | Каталог решти країн | Усі 7 країн завантажуються |
| **3** | `OLXParser` | Парсер працює + тест |
| **4** | `DimriaParser`, `KleinanzeigenParser`, `HabitacliaParser` | Усі парсери працюють |
| **5** | БД (Turso) | Таблиці створюються |
| **6** | `services.user`, `services.notifier` | Підписки, повідомлення |
| **7** | `services.aggregator` | Цикл + дедуплікація |
| **8** | Бот | Реагує на команди |
| **9** | Flask + scheduler | Застосунок працює |
| **10** | Міграція v1 → v2 | Старі slug'и → нові |
| **11** | Деплой на Render | Бот у проді |
| **12** | CI | Тести на PR |

---

## 11. Що ми НЕ робимо

- ❌ Не тримаємо старі `CITIES`, `CITY_ID_TO_NAME`, `resolve_city_id` — **видаляємо повністю** після етапу 10.
- ❌ Не робимо `if source_key == 'olx': ...` — усе через `PARSER_REGISTRY`.
- ❌ Не зберігаємо ID міст поза контекстом `source_key`.
- ❌ Не додаємо поля «для сумісності» — або нове, або старе.
- ❌ Не робимо `_get_country_for_location()` — країна завжди відома з `City.country`.

---

## 13. Статус реалізації

| Етап | Статус |
|------|--------|
| 0. Каркас пакета | ⏳ |
| 1. Каталог + UA | ⏳ |
| 2. Каталог решти країн | ⏳ |
| 3. OLXParser | ⏳ |
| 4. DimriaParser, Kleinanzeigen, Habitaclia | ⏳ |
| 5. БД | ⏳ |
| 6. services.user, services.notifier | ⏳ |
| 7. services.aggregator | ⏳ |
| 8. Бот | ⏳ |
| 9. Flask + scheduler | ⏳ |
| 10. Міграція даних | ⏳ |
| 11. Деплой | ⏳ |
| 12. CI | ⏳ |