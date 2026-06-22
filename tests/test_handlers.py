import asyncio
from unittest.mock import AsyncMock, MagicMock

from bot.handlers import MAX_MESSAGE_LENGTH, handle_guest_query, handle_text, help_cmd, start
from bot.prompts import HELP_TEXT, START_TEXT


def _make_update(text="hello", user_id=123):
    update = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id
    return update


def _make_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    context.bot_data = {
        "complete": AsyncMock(return_value=reply),
        "allowed_user_ids": allowed,
    }
    return context


def _make_guest_update(text="hello", user_id=123, query_id="qid123"):
    update = MagicMock()
    update.guest_message.text = text
    update.guest_message.guest_query_id = query_id
    update.guest_message.from_user.id = user_id
    update.guest_message.guest_bot_caller_user = MagicMock()
    return update


def _make_guest_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    context.bot.answer_guest_query = AsyncMock()
    context.bot_data = {
        "complete": AsyncMock(return_value=reply),
        "allowed_user_ids": allowed,
    }
    return context


# --- handle_text ---

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


def test_handle_text_rejects_unauthorized_user():
    update = _make_update(user_id=999)
    context = _make_context(allowed=frozenset({123}))
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "not authorized" in update.message.reply_text.call_args.args[0]
    context.bot_data["complete"].assert_not_awaited()


def test_handle_text_allows_any_when_no_restrictions():
    update = _make_update(user_id=999)
    context = _make_context()
    asyncio.run(handle_text(update, context))
    context.bot_data["complete"].assert_awaited_once()


def test_handle_text_no_user_blocked_when_allowlist_set():
    update = _make_update()
    update.effective_user = None
    context = _make_context(allowed=frozenset({123}))
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "not authorized" in update.message.reply_text.call_args.args[0]
    context.bot_data["complete"].assert_not_awaited()


def test_handle_text_rejects_overlong_message():
    long_text = "a" * (MAX_MESSAGE_LENGTH + 1)
    update = _make_update(text=long_text)
    context = _make_context()
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "too long" in update.message.reply_text.call_args.args[0].lower()
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


# --- handle_guest_query ---

def test_handle_guest_query_replies_with_llm_output():
    update = _make_guest_update(text="what is 2+2")
    context = _make_guest_context(reply="4")
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete"].assert_awaited_once_with("what is 2+2")
    context.bot.answer_guest_query.assert_awaited_once()


def test_handle_guest_query_rejects_unauthorized_user():
    update = _make_guest_update(user_id=999)
    context = _make_guest_context(allowed=frozenset({123}))
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete"].assert_not_awaited()
    context.bot.answer_guest_query.assert_awaited_once()


def test_handle_guest_query_noop_when_no_guest_message():
    update = MagicMock()
    update.guest_message = None
    context = _make_guest_context()
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete"].assert_not_awaited()
    context.bot.answer_guest_query.assert_not_awaited()


def test_handle_guest_query_noop_when_no_text():
    update = _make_guest_update(text="")
    context = _make_guest_context()
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete"].assert_not_awaited()
