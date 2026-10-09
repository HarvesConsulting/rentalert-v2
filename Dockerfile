# ─────────────────────────────────────────────────────────────
# RentAlert v2 — Dockerfile
#
# Використовує офіційний образ Playwright з Python 3.11 + Chromium.
# Потрібен для підтримки Spotahome-парсера на проді.
# ─────────────────────────────────────────────────────────────

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Робоча директорія
WORKDIR /app

# Змінні середовища
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 1. Копіюємо метадані проекту
COPY pyproject.toml README.md ./

# 2. Копіюємо код і дані
COPY src/ ./src/
COPY data/ ./data/

# 3. Встановлюємо залежності (включно з playwright)
RUN pip install --upgrade pip && \
    pip install -e ".[playwright]"

# 4. Health check (Render сам перевіряє /health)
EXPOSE 10000

# 5. Команда запуску
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 "rentalert.app:app"
