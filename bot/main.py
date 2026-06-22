import logging

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from . import openai_client
from .config import load_settings
from .handlers import handle_guest_query, handle_text, help_cmd, start

_log = logging.getLogger(__name__)


async def _log_update(update: Update, context) -> None:
    if update.guest_message:
        m = update.guest_message
        caller = m.guest_bot_caller_user
        frm = m.from_user
        chat = m.chat
        frm_str = (
            f"{frm.full_name} (@{frm.username}, id={frm.id})" if frm else "unknown"
        )
        caller_str = (
            f"{caller.full_name} (@{caller.username}, id={caller.id})"
            if caller
            else "unknown"
        )
        chat_str = (
            getattr(chat, "title", None)
            or getattr(chat, "full_name", None)
            or str(chat.id)
        )
        _log.info(
            "\n[GUEST UPDATE #%s]\n"
            "  Mentioned by : %s\n"
            "  Caller       : %s\n"
            "  Chat         : %s [%s, id=%s]\n"
            "  query_id     : %s",
            update.update_id,
            frm_str,
            caller_str,
            chat_str,
            chat.type,
            chat.id,
            m.guest_query_id,
        )
    else:
        update_type = next(
            (t for t in Update.ALL_TYPES if getattr(update, t, None) is not None),
            "unknown",
        )
        _log.info("[UPDATE #%s] type=%s", update.update_id, update_type)


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.bot_data["complete"] = lambda text: openai_client.complete(
        settings.llm_model, settings.llm_api_key, text
    )
    app.bot_data["allowed_user_ids"] = settings.allowed_user_ids

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(
        MessageHandler(filters.UpdateType.GUEST_MESSAGE, handle_guest_query)
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(TypeHandler(Update, _log_update), group=1)

    app.run_polling(allowed_updates=Update.ALL_TYPES)
