import os
import logging
from pathlib import Path
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# New imports for modular structure
from bot.core.task_processor import TaskProcessor
from bot.core.project_manager import ProjectManager
from bot.core.reminder_manager import ReminderManager
from bot.core.obsidian_manager import ObsidianManager
from bot.core.social_media_manager import SocialMediaManager # New import

from bot.handlers.task_handlers import task_command
from bot.handlers.project_handlers import project_command
from bot.handlers.reminder_handlers import remind_command
from bot.handlers.social_media_handlers import social_command # New import
from bot.handlers.common import auth_check, restricted_access, start # Import start

# ── Config ──────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GH_TOKEN = os.environ["GH_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_IDS = [int(uid) for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",") if uid]
REPO_PATH = os.environ.get("REPO_PATH", "/repo")
TARGET_ENVIRONMENT = os.environ.get("TARGET_ENV", "dev")  # "dev" or "prod"
OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "/obsidian_vault") # New config for Obsidian
X_API_KEY = os.environ.get("X_API_KEY") # New config for X/Twitter
X_API_SECRET = os.environ.get("X_API_SECRET") # New config for X/Twitter

# Data directory for managers (TinyDB, etc.)
DATA_DIR = Path(os.environ.get("BOT_DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Main ────────────────────────────────────────────────

async def post_init(application: Application):
    """Callback function to run after the bot has started."""
    log.info("Bot application started.")

    # Initialize managers and store them in bot_data
    # This makes them accessible from handlers via context.application.bot_data
    application.bot_data["task_processor"] = TaskProcessor(REPO_PATH, GH_TOKEN, TARGET_ENVIRONMENT)
    application.bot_data["project_manager"] = ProjectManager(DATA_DIR)
    # Pass application instance for ReminderManager to send messages
    application.bot_data["reminder_manager"] = ReminderManager(DATA_DIR, application) 
    application.bot_data["obsidian_manager"] = ObsidianManager(OBSIDIAN_VAULT_PATH)
    application.bot_data["social_media_manager"] = SocialMediaManager(DATA_DIR, X_API_KEY, X_API_SECRET) # Initialize social media manager
    
    log.info("All managers initialized and stored in bot_data.")

async def pre_shutdown(application: Application):
    """Callback function to run before the bot shuts down."""
    log.info("Bot application shutting down.")
    # Stop scheduler gracefully
    if "reminder_manager" in application.bot_data:
        application.bot_data["reminder_manager"].scheduler.shutdown()
        log.info("Reminder scheduler shut down.")


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).pre_shutdown(pre_shutdown).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("task", task_command))
    application.add_handler(CommandHandler("project", project_command))
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("social", social_command)) # New social media command handler

    # Add a catch-all for unauthorized users *only if* ALLOWED_USER_IDS is configured
    if ALLOWED_USER_IDS:
        unauthorized_filter = filters.COMMAND & ~filters.User(user_id=ALLOWED_USER_IDS)
        application.add_handler(MessageHandler(unauthorized_filter, restricted_access))
        log.info("Restricted access handler registered for unauthorized users.")
    else:
        log.info("ALLOWED_USER_IDS is empty. Bot accessible to all users.")
    
    log.info("All command handlers registered. Polling for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
