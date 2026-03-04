import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import auth_check, restricted_access
from bot.core.task_processor import TaskProcessor # Import the class

log = logging.getLogger(__name__)

async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /task command to generate code and open a PR."""
    user_id = update.effective_user.id
    if not auth_check(user_id):
        await restricted_access(update, context)
        return

    if not context.args:
        await update.message.reply_text(
            "Please provide a task description, e.g., `/task Add a new endpoint for user registration`"
        )
        return

    task_description = " ".join(context.args)
    chat_id = update.effective_chat.id

    await update.message.reply_text(
        f"🤖 Understood: '{task_description}'. Initiating code generation and PR process. This may take a few minutes..."
    )

    try:
        # Access TaskProcessor from bot_data
        task_processor: TaskProcessor = context.application.bot_data["task_processor"]
        result = await task_processor.process_task(task_description, chat_id)
        await update.message.reply_text(result)
    except Exception as e:
        log.exception(f"Error processing task for chat_id {chat_id}: {e}")
        await update.message.reply_text(f"An unexpected error occurred: {e}")
