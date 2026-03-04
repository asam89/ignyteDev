import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import auth_check, restricted_access, get_managers
from bot.core.reminder_manager import ReminderManager

log = logging.getLogger(__name__)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /remind command for setting reminders."""
    user_id = update.effective_user.id
    if not auth_check(user_id):
        await restricted_access(update, context)
        return

    if not context.args or len(context.args) < 3: # e.g., /remind 2024-12-31 10:00 Task message
        await update.message.reply_text(
            "Usage: `/remind YYYY-MM-DD HH:MM <message>`. Example: `/remind 2024-12-31 10:00 Review Q4 report`"
        )
        return

    managers = get_managers(context)
    reminder_manager: ReminderManager = managers.get("reminder_manager")
    if not reminder_manager:
        await update.message.reply_text("Reminder manager not initialized. Please check bot configuration.")
        return

    try:
        date_str = context.args[0]
        time_str = context.args[1]
        message = " ".join(context.args[2:])
        
        remind_at_str = f"{date_str} {time_str}"
        remind_at = datetime.strptime(remind_at_str, "%Y-%m-%d %H:%M")

        if remind_at < datetime.now():
            await update.message.reply_text("Cannot set a reminder in the past!")
            return

        chat_id = update.effective_chat.id
        reminder = await reminder_manager.add_reminder(chat_id, message, remind_at)
        await update.message.reply_text(
            f"✅ Reminder set for {remind_at.strftime('%Y-%m-%d %H:%M')}: '{message}'"
        )

    except ValueError:
        await update.message.reply_text(
            "Invalid date/time format. Please use `YYYY-MM-DD HH:MM`. Example: `/remind 2024-12-31 10:00 Task message`"
        )
    except Exception as e:
        log.exception(f"Error setting reminder: {e}")
        await update.message.reply_text(f"An error occurred while setting the reminder: {e}")
