import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.handlers import handle_text, help_cmd, start
from bot.prompts import HELP_TEXT, START_TEXT


def _make_update(text="hello", chat_id=123):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_chat.id = chat_id
    return update


def _make_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    context.bot_data = {
        "complete": AsyncMock(return_value=reply),
        "allowed_chat_ids": allowed,
    }
    return context


def test_handle_text_replies_with_llm_output():
    update = _make_update("hello")
    context = _make_context(reply="the answer")
    asyncio.run(handle_text(update, context))
    context.bot_data["complete"].assert_awaited_once_with("hello")
    update.message.reply_text.assert_awaited_once_with("the answer")


def test_handle_text_friendly_error_on_llm_failure():
    update = _make_update("boom")
    context = _make_context()
    context.bot_data["complete"].side_effect = RuntimeError("llm down")
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "went wrong" in update.message.reply_text.call_args.args[0]


def test_handle_text_rejects_unauthorized_chat():
    update = _make_update(chat_id=999)
    context = _make_context(allowed=frozenset({123}))
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "not authorized" in update.message.reply_text.call_args.args[0]
    context.bot_data["complete"].assert_not_awaited()


def test_handle_text_no_message_is_noop():
    update = _make_update()
    update.message = None
    context = _make_context()
    asyncio.run(handle_text(update, context))  # must not raise
    context.bot_data["complete"].assert_not_awaited()


def test_start_sends_welcome():
    update = _make_update()
    asyncio.run(start(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(START_TEXT)


def test_help_sends_usage():
    update = _make_update()
    asyncio.run(help_cmd(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(HELP_TEXT)
