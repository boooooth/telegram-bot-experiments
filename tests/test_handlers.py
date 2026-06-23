import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import (
    _TRUNCATION_NOTICE,
    MAX_INLINE_TEXT,
    MAX_MESSAGE_LENGTH,
    _clip,
    handle_guest_query,
    handle_text,
    help_cmd,
    start,
)
from bot.prompts import HELP_TEXT, START_TEXT


def _make_update(text="hello", user_id=123, chat_type="private"):
    update = MagicMock()
    update.message.text = text
    update.message.message_id = 1
    update.message.reply_text = AsyncMock()
    update.effective_user.id = user_id
    update.effective_chat.id = 100
    update.effective_chat.type = chat_type
    return update


def _make_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    context.bot.send_message_draft = AsyncMock()
    context.bot.send_chat_action = AsyncMock()

    async def _stream_reply(*args):
        yield reply

    context.bot_data = {
        "complete": AsyncMock(return_value=reply),
        "complete_stream": MagicMock(side_effect=_stream_reply),
        "allowed_user_ids": allowed,
    }
    return context


def _make_guest_update(text="hello", user_id=123, query_id="qid123"):
    update = MagicMock()
    update.guest_message.text = text
    update.guest_message.guest_query_id = query_id
    update.guest_message.from_user.id = user_id
    update.guest_message.guest_bot_caller_user = MagicMock()
    update.guest_message.reply_to_message = None
    update.guest_message.chat.id = 200
    return update


def _make_guest_context(reply="hi back", allowed=frozenset()):
    context = MagicMock()
    sent = MagicMock()
    sent.inline_message_id = "inline-123"
    context.bot.answer_guest_query = AsyncMock(return_value=sent)
    context.bot.edit_message_text = AsyncMock()

    async def _stream_reply(*args):
        yield reply

    context.bot_data = {
        "complete_stream": MagicMock(side_effect=_stream_reply),
        "allowed_user_ids": allowed,
    }
    return context


# --- _clip ---


def test_clip_short_text_unchanged():
    assert _clip("hello world", 100) == "hello world"


def test_clip_truncates_within_limit():
    long_text = "word " * 2000  # well over MAX_INLINE_TEXT chars
    result = _clip(long_text, MAX_INLINE_TEXT)
    assert len(result) <= MAX_INLINE_TEXT
    assert result.endswith(_TRUNCATION_NOTICE)


def test_clip_cuts_at_word_boundary():
    # "aaa bbb " + lots of x's — should cut before the x block, not mid-word
    text = "aaa bbb " + "x" * MAX_INLINE_TEXT
    result = _clip(text, MAX_INLINE_TEXT)
    body = result[: -len(_TRUNCATION_NOTICE)]
    assert not body.strip().endswith("x")


# --- handle_text ---


def test_handle_text_replies_with_llm_output():
    update = _make_update("hello")
    context = _make_context(reply="the answer")
    asyncio.run(handle_text(update, context))
    context.bot_data["complete_stream"].assert_called_once_with("hello")
    update.message.reply_text.assert_awaited_once_with("the answer")


def test_handle_text_friendly_error_on_llm_failure():
    update = _make_update("boom")
    context = _make_context()
    context.bot_data["complete_stream"].side_effect = RuntimeError("llm down")
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "went wrong" in update.message.reply_text.call_args.args[0]


def test_handle_text_rejects_unauthorized_user():
    update = _make_update(user_id=999)
    context = _make_context(allowed=frozenset({123}))
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "not authorized" in update.message.reply_text.call_args.args[0]
    context.bot_data["complete_stream"].assert_not_called()


def test_handle_text_allows_any_when_no_restrictions():
    update = _make_update(user_id=999)
    context = _make_context()
    asyncio.run(handle_text(update, context))
    context.bot_data["complete_stream"].assert_called_once()


def test_handle_text_no_user_blocked_when_allowlist_set():
    update = _make_update()
    update.effective_user = None
    context = _make_context(allowed=frozenset({123}))
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "not authorized" in update.message.reply_text.call_args.args[0]
    context.bot_data["complete_stream"].assert_not_called()


def test_handle_text_rejects_overlong_message():
    long_text = "a" * (MAX_MESSAGE_LENGTH + 1)
    update = _make_update(text=long_text)
    context = _make_context()
    asyncio.run(handle_text(update, context))
    update.message.reply_text.assert_awaited_once()
    assert "too long" in update.message.reply_text.call_args.args[0].lower()
    context.bot_data["complete_stream"].assert_not_called()


def test_handle_text_no_message_is_noop():
    update = _make_update()
    update.message = None
    context = _make_context()
    asyncio.run(handle_text(update, context))
    context.bot_data["complete_stream"].assert_not_called()


def test_handle_text_private_uses_draft():
    update = _make_update(chat_type="private")
    context = _make_context()
    asyncio.run(handle_text(update, context))
    context.bot.send_message_draft.assert_awaited()


def test_handle_text_group_skips_draft():
    update = _make_update(chat_type="group")
    context = _make_context()
    asyncio.run(handle_text(update, context))
    context.bot.send_message_draft.assert_not_awaited()


def test_handle_text_group_starts_typing_task():
    update = _make_update(chat_type="group")
    context = _make_context()
    with patch("bot.handlers.asyncio.create_task") as mock_create_task:
        mock_create_task.return_value = MagicMock()
        asyncio.run(handle_text(update, context))
        # close the unawaited coroutine to suppress the warning
        mock_create_task.call_args.args[0].close()
    mock_create_task.assert_called_once()


def test_start_sends_welcome():
    update = _make_update()
    asyncio.run(start(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(START_TEXT)


def test_help_sends_usage():
    update = _make_update()
    asyncio.run(help_cmd(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with(HELP_TEXT)


# --- handle_guest_query ---


def test_handle_guest_query_sends_placeholder_then_edits():
    update = _make_guest_update(text="what is 2+2")
    context = _make_guest_context(reply="4")
    asyncio.run(handle_guest_query(update, context))
    # placeholder "…" sent first via answer_guest_query
    call_result = context.bot.answer_guest_query.call_args.kwargs["result"]
    assert call_result.input_message_content.message_text == "…"
    # final reply delivered via edit_message_text
    context.bot.edit_message_text.assert_awaited()
    edit_kwargs = context.bot.edit_message_text.call_args.kwargs
    assert edit_kwargs["text"] == "4"
    assert edit_kwargs["inline_message_id"] == "inline-123"


def test_handle_guest_query_rejects_unauthorized_user():
    update = _make_guest_update(user_id=999)
    context = _make_guest_context(allowed=frozenset({123}))
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete_stream"].assert_not_called()
    context.bot.answer_guest_query.assert_awaited_once()
    call_result = context.bot.answer_guest_query.call_args.kwargs["result"]
    assert "not authorized" in call_result.input_message_content.message_text


def test_handle_guest_query_noop_when_no_guest_message():
    update = MagicMock()
    update.guest_message = None
    context = _make_guest_context()
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete_stream"].assert_not_called()
    context.bot.answer_guest_query.assert_not_awaited()


def test_handle_guest_query_noop_when_no_text():
    update = _make_guest_update(text="")
    context = _make_guest_context()
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete_stream"].assert_not_called()


def test_handle_guest_query_includes_reply_context():
    update = _make_guest_update(text="explain this")
    replied = MagicMock()
    replied.text = "def foo(): pass"
    update.guest_message.reply_to_message = replied
    context = _make_guest_context()
    asyncio.run(handle_guest_query(update, context))
    called_prompt = context.bot_data["complete_stream"].call_args.args[0]
    assert "def foo(): pass" in called_prompt
    assert "explain this" in called_prompt


def test_handle_guest_query_no_reply_context():
    update = _make_guest_update(text="what is recursion")
    update.guest_message.reply_to_message = None
    context = _make_guest_context()
    asyncio.run(handle_guest_query(update, context))
    context.bot_data["complete_stream"].assert_called_once_with("what is recursion")
