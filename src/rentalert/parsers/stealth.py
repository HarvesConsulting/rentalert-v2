"""Спільні утиліти для парсерів: ротація UA, заголовки, затримки, retry.

Використання у парсері:
    from rentalert.parsers.stealth import stealth_headers, human_delay

    human_delay()
    response = cffi_requests.get(url, headers=stealth_headers(), ...)
"""

from __future__ import annotations

import logging
import random
import time

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# User-Agents (реалістичні, актуальні версії Chrome)
# ─────────────────────────────────────────────────────────────

USER_AGENTS: list[str] = [
    # Windows + Chrome 131
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # macOS + Chrome 131
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Linux + Chrome 131
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Windows + Chrome 130
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


# ─────────────────────────────────────────────────────────────
# Заголовки
# ─────────────────────────────────────────────────────────────


def stealth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Повертає реалістичні заголовки з випадковим User-Agent.

    Args:
        extra: додаткові заголовки, які треба додати/перекрити.
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9,pl;q=0.8,uk;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if extra:
        headers.update(extra)
    return headers


# ─────────────────────────────────────────────────────────────
# Затримки
# ─────────────────────────────────────────────────────────────


def human_delay(min_sec: float = 1.5, max_sec: float = 4.0) -> None:
    """Людиноподібна затримка між запитами.

    Використовує рівномірний розподіл, а не фіксоване значення,
    щоб патерн запитів не був «механічним».
    """
    delay = random.uniform(min_sec, max_sec)
    log.debug("stealth: пауза %.2f сек", delay)
    time.sleep(delay)


# ─────────────────────────────────────────────────────────────
# Retry
# ─────────────────────────────────────────────────────────────


RETRY_CODES: set[int] = {429, 500, 502, 503, 504}


def fetch_with_retry(
    http_get,
    url: str,
    *,
    retries: int = 2,
    backoff_sec: int = 5,
    **kwargs,
):
    """Робить HTTP-запит з retry на 429/5xx.

    Args:
        http_get: функція запиту (cffi_requests.get або session.get).
        url: URL.
        retries: скільки додаткових спроб (0 = без retry).
        backoff_sec: базова пауза між спробами (множиться на номер спроби).
        **kwargs: решта аргументів для http_get.

    Returns:
        Response або None, якщо всі спроби провалились.
    """
    last_response = None

    for attempt in range(retries + 1):
        try:
            response = http_get(url, **kwargs)
        except Exception as e:
            log.warning(
                "stealth: запит впав (спроба %d/%d): %s",
                attempt + 1,
                retries + 1,
                e,
            )
            if attempt < retries:
                wait = backoff_sec * (attempt + 1)
                log.info("stealth: чекаю %d сек і повторюю", wait)
                time.sleep(wait)
                continue
            return None

        if response.status_code in RETRY_CODES:
            last_response = response
            log.warning(
                "stealth: HTTP %d (спроба %d/%d) — %s",
                response.status_code,
                attempt + 1,
                retries + 1,
                url,
            )
            if attempt < retries:
                wait = backoff_sec * (attempt + 1)
                log.info("stealth: чекаю %d сек і повторюю", wait)
                time.sleep(wait)
                continue

        return response

    return last_response
