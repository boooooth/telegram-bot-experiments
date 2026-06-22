import logging

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ContextTypes

from .prompts import HELP_TEXT, START_TEXT

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(HELP_TEXT)


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
        reply = await context.bot_data["complete"](message.text)
        await context.bot.answer_guest_query(
            guest_query_id=message.guest_query_id,
            result=InlineQueryResultArticle(
                id="1",
                title="Answer",
                input_message_content=InputTextMessageContent(message_text=reply),
            ),
        )
        logger.info("answered guest query from user_id=%s", caller.id if caller else "unknown")
    except Exception:
        logger.exception("LLM call failed for guest query")


MAX_MESSAGE_LENGTH = 4_000


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
    if len(text) > MAX_MESSAGE_LENGTH:
        await update.message.reply_text(
            f"Your message is too long ({len(text):,} chars). "
            f"Please keep it under {MAX_MESSAGE_LENGTH:,} characters."
        )
        logger.info("message too long from user_id=%s (%d chars)", user_id, len(text))
        return
    logger.info("message from user_id=%s", user_id)
    try:
        reply = await context.bot_data["complete"](text)
        await update.message.reply_text(reply)
        logger.info("replied to user_id=%s", user_id)
    except Exception:
        logger.exception("LLM call failed for user_id=%s", user_id)
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again in a moment."
        )
