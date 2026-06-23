import asyncio
import logging
import time

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ContextTypes

from .prompts import HELP_TEXT, START_TEXT

_DRAFT_UPDATE_INTERVAL = 1.0  # seconds between sendMessageDraft calls
_EDIT_UPDATE_INTERVAL = 0.5  # seconds between editMessageText calls (guest streaming)
_EDIT_MIN_NEW_CHARS = 10  # minimum new characters before an intermediate edit is worth sending

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(HELP_TEXT)


async def _keep_typing(bot, chat_id: int) -> None:
    while True:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(4)


_TRUNCATION_NOTICE = "\n\n(reply truncated — message me directly for the full answer)"


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    hard_limit = limit - len(_TRUNCATION_NOTICE)
    cut = text.rfind(" ", 0, hard_limit)
    return text[: cut if cut > 0 else hard_limit] + _TRUNCATION_NOTICE


async def handle_guest_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.guest_message
    if message is None or not message.text or not message.guest_query_id:
        return

    user_id = message.from_user.id if message.from_user else None
    allowed_user_ids = context.bot_data.get("allowed_user_ids", frozenset())
    if allowed_user_ids and (not user_id or user_id not in allowed_user_ids):
        logger.info("unauthorized guest query from user_id=%s", user_id)
        await context.bot.answer_guest_query(
            guest_query_id=message.guest_query_id,
            result=InlineQueryResultArticle(
                id="1",
                title="Unauthorized",
                input_message_content=InputTextMessageContent(
                    message_text="Sorry, you are not authorized to use this bot."
                ),
            ),
        )
        return

    caller = message.guest_bot_caller_user
    logger.info("guest query from user_id=%s", caller.id if caller else "unknown")
    try:
        replied_to = message.reply_to_message
        if replied_to and replied_to.text:
            prompt = (
                f"The user is referring to this message:\n{replied_to.text}"
                f"\n\nUser's request: {message.text}"
            )
        else:
            prompt = message.text

        sent = await context.bot.answer_guest_query(
            guest_query_id=message.guest_query_id,
            result=InlineQueryResultArticle(
                id="1",
                title="Answer",
                input_message_content=InputTextMessageContent(message_text="…"),
            ),
        )
        inline_message_id = sent.inline_message_id

        accumulated = ""
        last_sent = "…"
        last_edit = time.monotonic()
        async for chunk in context.bot_data["complete_stream"](prompt):
            accumulated += chunk
            if time.monotonic() - last_edit >= _EDIT_UPDATE_INTERVAL:
                clipped = _clip(accumulated, MAX_INLINE_TEXT)
                if len(clipped) - len(last_sent) >= _EDIT_MIN_NEW_CHARS:
                    try:
                        await context.bot.edit_message_text(
                            inline_message_id=inline_message_id,
                            text=clipped,
                        )
                        last_sent = clipped
                    except Exception:
                        pass  # rate-limited or transient; final edit still delivers the full reply
                last_edit = time.monotonic()

        final = _clip(accumulated, MAX_INLINE_TEXT)
        if final != last_sent:
            await context.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=final,
            )
        logger.info("answered guest query from user_id=%s", caller.id if caller else "unknown")
    except Exception:
        logger.exception("LLM call failed for guest query")


MAX_MESSAGE_LENGTH = 4_000
MAX_INLINE_TEXT = 4_096
BLOCK_SIZE = 4_096


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return
    user_id = update.effective_user.id if update.effective_user else None
    allowed_user_ids = context.bot_data.get("allowed_user_ids", frozenset())
    if allowed_user_ids and (not user_id or user_id not in allowed_user_ids):
        await update.message.reply_text("Sorry, you are not authorized to use this bot.")
        logger.info("unauthorized access attempt from user_id=%s", user_id)
        return
    text = update.message.text
    if not text:
        return
    if len(text) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text(
            f"Your message is too long ({len(text):,} chars). "
            f"Please keep it under {MAX_MESSAGE_LENGTH:,} characters."
        )
        logger.info("message too long from user_id=%s (%d chars)", user_id, len(text))
        return
    logger.info("message from user_id=%s", user_id)
    chat_id = update.effective_chat.id
    is_private = update.effective_chat.type == "private"
    base_draft_id = update.message.message_id
    block_count = 0
    draft_id = base_draft_id
    typing_task = None
    try:
        if is_private:
            await context.bot.send_message_draft(chat_id=chat_id, draft_id=draft_id, text="")
        else:
            typing_task = asyncio.create_task(_keep_typing(context.bot, chat_id))
        accumulated = ""
        last_update = time.monotonic()
        async for chunk in context.bot_data["complete_stream"](text):
            accumulated += chunk
            if len(accumulated) >= BLOCK_SIZE:
                await update.message.reply_text(accumulated[:BLOCK_SIZE])
                accumulated = accumulated[BLOCK_SIZE:]
                block_count += 1
                draft_id = base_draft_id + block_count
                last_update = time.monotonic()
                if is_private:
                    await context.bot.send_message_draft(
                        chat_id=chat_id, draft_id=draft_id, text=""
                    )
            elif is_private and time.monotonic() - last_update >= _DRAFT_UPDATE_INTERVAL:
                await context.bot.send_message_draft(
                    chat_id=chat_id, draft_id=draft_id, text=accumulated
                )
                last_update = time.monotonic()
        if accumulated:
            await update.message.reply_text(accumulated)
        logger.info("replied to user_id=%s", user_id)
    except Exception:
        logger.exception("LLM call failed for user_id=%s", user_id)
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again in a moment."
        )
    finally:
        if typing_task:
            typing_task.cancel()
