"""Тести для обробки платежів Telegram Stars."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rentalert.bot import callbacks

# ─── _handle_buy ───


@pytest.fixture
def ctx() -> MagicMock:
    """Мокований BotContext."""
    ctx = MagicMock()
    ctx.notifier = MagicMock()
    ctx.notifier.send_invoice.return_value = True
    ctx.notifier.answer_callback.return_value = True
    ctx.client = MagicMock()
    return ctx


def test_buy_monthly_sends_invoice_300(ctx) -> None:
    """Місяць = 300 ⭐."""
    callbacks._handle_buy("monthly", "123", "cb_id", ctx)

    assert ctx.notifier.send_invoice.called
    call_args = ctx.notifier.send_invoice.call_args
    assert call_args.kwargs["amount_stars"] == 300
    assert call_args.kwargs["payload"] == "sub:monthly:300"
    assert "1 місяць" in call_args.kwargs["title"]


def test_buy_yearly_sends_invoice_2000(ctx) -> None:
    """Рік = 2000 ⭐."""
    callbacks._handle_buy("yearly", "123", "cb_id", ctx)

    assert ctx.notifier.send_invoice.called
    call_args = ctx.notifier.send_invoice.call_args
    assert call_args.kwargs["amount_stars"] == 2000
    assert call_args.kwargs["payload"] == "sub:yearly:2000"
    assert "12 місяців" in call_args.kwargs["title"]


def test_buy_invalid_period_rejected(ctx) -> None:
    """Невідомий період → помилка, без invoice."""
    callbacks._handle_buy("weekly", "123", "cb_id", ctx)

    assert not ctx.notifier.send_invoice.called
    # answer_callback з "❌"
    assert ctx.notifier.answer_callback.called
    args = ctx.notifier.answer_callback.call_args
    assert "❌" in args.args[1]


def test_buy_answers_callback_first(ctx) -> None:
    """Спочатку answer_callback, потім send_invoice."""
    callbacks._handle_buy("monthly", "123", "cb_id", ctx)

    # answer_callback викликано
    assert ctx.notifier.answer_callback.called
    assert ctx.notifier.answer_callback.call_args.args[0] == "cb_id"


def test_buy_invoice_failed_no_crash(ctx) -> None:
    """Якщо send_invoice повертає False → не падає, надсилає повідомлення."""
    ctx.notifier.send_invoice.return_value = False

    callbacks._handle_buy("monthly", "123", "cb_id", ctx)

    # send_invoice викликано, але повернув False
    assert ctx.notifier.send_invoice.called
    # send_message викликано з помилкою
    assert ctx.notifier.send_message.called
