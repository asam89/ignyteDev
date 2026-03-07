import os
import logging
from telegram import Update
from telegram.ext import ContextTypes

log = logging.getLogger(__name__)

# Config from environment, or use global config from worker_node
# For common, it's safer to have these passed or imported carefully.
# For now, let's assume `ALLOWED_USER_IDS` is available globally or passed.

ALLOWED_USER_IDS = [int(uid) for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",") if uid]

def auth_check(user_id: int) -> bool:
    """Only allow whitelisted Telegram user IDs."""
    if not ALLOWED_USER_IDS:
        return True  # No whitelist = open (not recommended for prod)
    return user_id in ALLOWED_USER_IDS

async def restricted_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message indicating restricted access."""
    await update.message.reply_text("🚫 You are not authorized to use this bot.")
    log.warning(f"Unauthorized access attempt by user ID: {update.effective_user.id}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    user_id = update.effective_user.id
    if not auth_check(user_id):
        await restricted_access(update, context)
        return

    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm your autonomous developer bot. How can I assist you today?"
        "Try /task, /project, /remind, or /social."
    )
    log.info(f"User {user_id} started the bot.")

def get_managers(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Helper to get managers from bot_data."""
    # Ensure these are initialized in worker_node.py and stored in context.application.bot_data
    return {
        "project_manager": context.application.bot_data.get("project_manager"),
        "reminder_manager": context.application.bot_data.get("reminder_manager"),
        "obsidian_manager": context.application.bot_data.get("obsidian_manager"),
        "social_media_manager": context.application.bot_data.get("social_media_manager"), # Add social media manager
    }
