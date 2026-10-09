# ─────────────────────────────────────────────────────────────
# RentAlert v2 — Dockerfile
#
# Python 3.11 + Playwright + Chromium
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/ ./data/

RUN pip install --upgrade pip && \
    pip install -e ".[playwright]"

RUN playwright install chromium && \
    playwright install-deps chromium

EXPOSE 10000

CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 "rentalert.app:app"
