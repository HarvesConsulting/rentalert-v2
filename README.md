# RentAlert v2

Telegram-бот — агрегатор оголошень про оренду житла з кількох джерел.

## Що робить

- Відстежує **нові** оголошення на OLX, DIM.RIA, Kleinanzeigen, Habitaclia
- Надсилає їх у Telegram
- Користувач обирає країну, місто, джерела
- Підтримує 7 країн: 🇺🇦 🇵🇱 🇵🇹 🇷🇴 🇧🇬 🇩🇪 🇪🇸

## Документація

- [ARCHITECTURE.md](./ARCHITECTURE.md) — архітектура, модель даних, план реалізації

## Вимоги

- Python 3.11 або 3.12
- Git

## Розробка

### Встановлення

```powershell
# 1. Клонувати репозиторій
git clone <repo-url>
cd rentalert-v2

# 2. Створити віртуальне середовище (Python 3.11)
py -3.11 -m venv .venv

# 3. Активувати
.venv\Scripts\Activate.ps1     # Windows
# source .venv/bin/activate     # Linux/Mac

# 4. Встановити залежності
pip install --upgrade pip
pip install -e ".[dev]"
```

### Налаштування

```powershell
Copy-Item .env.example .env
notepad .env
```

Заповни в `.env`:
- `TELEGRAM_BOT_TOKEN` — токен від [@BotFather](https://t.me/BotFather)
- `TELEGRAM_CHAT_ID` — твій ID від [@userinfobot](https://t.me/userinfobot)
- `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` — з [turso.tech](https://turso.tech)
- `DIMRIA_API_KEY` — з [developers.ria.com](https://developers.ria.com)
- `ADMIN_API_TOKEN` — згенеруй:
  ```powershell
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

### Запуск локально

```powershell
python -m renalert
```

Flask піднімається на `http://localhost:3000`. Перевірка:

```powershell
curl http://localhost:3000/health
# → ok
```

## Тести

```powershell
pytest                       # всі тести
pytest tests/catalog         # тільки каталог
pytest -k olx                # тести з "olx" у назві
pytest --cov=rentalert       # з покриттям
```

## Лінтер і форматування

```powershell
ruff check .                 # перевірка
ruff format .                # автоформатування
ruff check --fix .           # автовиправлення
mypy src/rentalert           # перевірка типів
```

## Структура проєкту

```
src/rentalert/
├── __init__.py
├── __main__.py              # точка входу (python -m renalert)
├── app.py                   # Flask application factory
├── config.py                # конфігурація з env
├── catalog/                 # довідник країн, джерел, міст
│   ├── models.py            # dataclass: Country, Source, City
│   ├── loader.py            # завантаження JSON → об'єкти
│   └── catalog.py           # клас Catalog (пошук, доступ)
├── parsers/                 # парсери джерел
│   ├── base.py              # Parser(ABC), Listing
│   ├── registry.py          # SOURCE_KEY → Parser
│   ├── olx.py               # OLXParser (усі olx_*)
│   ├── dimria.py            # DimriaParser
│   ├── kleinanzeigen.py     # KleinanzeigenParser
│   └── habitaclia.py        # HabitacliaParser
├── db/                      # робота з Turso
│   ├── client.py            # HTTP клієнт
│   ├── schema.py            # CREATE TABLE + міграції
│   └── queries.py           # високорівневі запити
├── services/                # бізнес-логіка
│   ├── aggregator.py        # головний цикл перевірки
│   ├── notifier.py          # Telegram повідомлення
│   └── user.py              # налаштування користувача
└── bot/                     # Telegram UI
    ├── handlers.py          # update → дія
    ├── callbacks.py         # обробка inline-кнопок
    ├── keyboards.py         # побудова клавіатур
    ├── states.py            # FSM
    └── ui_texts.py          # локалізовані тексти
```

## Статус

Дивись [ARCHITECTURE.md → Статус реалізації](./ARCHITECTURE.md#13-статус-реалізації).

## Ліцензія

Proprietary.