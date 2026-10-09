# ─────────────────────────────────────────────────────────────
# RentAlert v2 — Dockerfile
#
# Python 3.11, без Playwright/Chromium
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/ ./data/

RUN pip install --upgrade pip && \
    pip install -e .

EXPOSE 10000

CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 "rentalert.app:app"
