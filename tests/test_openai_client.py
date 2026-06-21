import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bot.openai_client import complete
from bot.prompts import SYSTEM_PROMPT


def _make_mock_response(content: str = "hello back"):
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = content
    return mock_resp


def test_calls_acompletion_once():
    with patch(
        "bot.openai_client.litellm.acompletion",
        new=AsyncMock(return_value=_make_mock_response()),
    ) as mock:
        asyncio.run(complete("gpt-4o-mini", "test-key", "hello"))
        mock.assert_called_once()


def test_messages_are_system_then_user():
    with patch(
        "bot.openai_client.litellm.acompletion",
        new=AsyncMock(return_value=_make_mock_response()),
    ) as mock:
        asyncio.run(complete("gpt-4o-mini", "test-key", "hello"))
        _, kwargs = mock.call_args
        messages = kwargs["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
        assert messages[1] == {"role": "user", "content": "hello"}


def test_model_is_passed_through():
    with patch(
        "bot.openai_client.litellm.acompletion",
        new=AsyncMock(return_value=_make_mock_response()),
    ) as mock:
        asyncio.run(complete("gpt-4o-mini", "test-key", "hello"))
        _, kwargs = mock.call_args
        assert kwargs["model"] == "gpt-4o-mini"


def test_returns_content():
    with patch(
        "bot.openai_client.litellm.acompletion",
        new=AsyncMock(return_value=_make_mock_response("the answer")),
    ):
        result = asyncio.run(complete("gpt-4o-mini", "test-key", "q"))
        assert result == "the answer"


def test_none_content_returns_empty_string():
    with patch(
        "bot.openai_client.litellm.acompletion",
        new=AsyncMock(return_value=_make_mock_response(None)),
    ):
        result = asyncio.run(complete("gpt-4o-mini", "test-key", "q"))
        assert result == ""
