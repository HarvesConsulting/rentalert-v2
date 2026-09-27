"""Тести для обробки платежів Telegram Stars."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rentalert.bot import callbacks


@pytest.fixture
def ctx() -> MagicMock:
    """Мокований BotContext з реальним catalog.country."""
    ctx = MagicMock()
    ctx.notifier = MagicMock()
    ctx.notifier.send_invoice.return_value = True
    ctx.notifier.answer_callback.return_value = True
    ctx.client = MagicMock()

    # ── Мокований country (для pt) ──
    country = MagicMock()
    country.price_stars = 100

    # catalog.country(code) → country
    ctx.catalog = MagicMock()
    ctx.catalog.country.return_value = country

    # user_svc.get_country → "pt"
    # user_svc.get_language → "uk"
    return ctx


@pytest.fixture(autouse=True)
def mock_user_svc(mocker):
    """Мокає user_svc.get_country і get_language."""
    mocker.patch(
        "rentalert.bot.callbacks.user_svc.get_country",
        return_value="pt",
    )
    mocker.patch(
        "rentalert.bot.callbacks.user_svc.get_language",
        return_value="uk",
    )


@pytest.fixture(autouse=True)
def mock_db_log(mocker):
    """Мокає db.log_activity (щоб не було JSON-помилок)."""
    mocker.patch("rentalert.bot.callbacks.db.log_activity")


# ─── _handle_buy ───


def test_buy_monthly_sends_invoice_100(ctx) -> None:
    """Місяць для pt = 100 ⭐."""
    callbacks._handle_buy("monthly", "123", "cb_id", ctx)

    assert ctx.notifier.send_invoice.called
    call_args = ctx.notifier.send_invoice.call_args
    assert call_args.kwargs["amount_stars"] == 100
    assert call_args.kwargs["payload"] == "sub:monthly:100"


def test_buy_yearly_sends_invoice_1020(ctx) -> None:
    """Рік для pt = 100 × 12 × 0.85 = 1020 ⭐."""
    callbacks._handle_buy("yearly", "123", "cb_id", ctx)

    assert ctx.notifier.send_invoice.called
    call_args = ctx.notifier.send_invoice.call_args
    assert call_args.kwargs["amount_stars"] == 1020
    assert call_args.kwargs["payload"] == "sub:yearly:1020"


def test_buy_invalid_period_rejected(ctx) -> None:
    """Невідомий період → помилка, без invoice."""
    callbacks._handle_buy("weekly", "123", "cb_id", ctx)

    assert not ctx.notifier.send_invoice.called
    assert ctx.notifier.answer_callback.called
    args = ctx.notifier.answer_callback.call_args
    assert "❌" in args.args[1]


def test_buy_answers_callback_first(ctx) -> None:
    """Спочатку answer_callback, потім send_invoice."""
    callbacks._handle_buy("monthly", "123", "cb_id", ctx)

    assert ctx.notifier.answer_callback.called
    assert ctx.notifier.answer_callback.call_args.args[0] == "cb_id"


def test_buy_invoice_failed_no_crash(ctx) -> None:
    """Якщо send_invoice повертає False → не падає, надсилає повідомлення."""
    ctx.notifier.send_invoice.return_value = False

    callbacks._handle_buy("monthly", "123", "cb_id", ctx)

    assert ctx.notifier.send_invoice.called
    assert ctx.notifier.send_message.called
