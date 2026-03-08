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
from bot.handlers.task_handlers import task_command
from bot.handlers.project_handlers import project_command
from bot.handlers.reminder_handlers import remind_command
from bot.handlers.common import auth_check, restricted_access # Import for main application setup

# ── Config ──────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GH_TOKEN = os.environ["GH_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_IDS = [int(uid) for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",") if uid]
REPO_PATH = os.environ.get("REPO_PATH", "/repo")
TARGET_ENVIRONMENT = os.environ.get("TARGET_ENV", "dev")  # "dev" or "prod"
OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH") # New config for Obsidian

# Data directory for managers (TinyDB, etc.)
DATA_DIR = Path(os.environ.get("BOT_DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Main ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    if not auth_check(user_id):
        await restricted_access(update, context)
        return
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm IgnyteDev, your autonomous development bot.\n\n"
        "You can assign me tasks, manage projects, and set reminders.\n"
        "Use /task <description> to assign a development task.\n"
        "Use /project <action> to manage projects.\n"
        "Use /remind YYYY-MM-DD HH:MM <message> to set a reminder."
    )
    log.info(f"User {user.id} ({user.username}) started the bot.")

async def post_init(application: Application):
    """Callback function to run after the bot has started."""
    log.info("Bot application started.")
    log.info(f"Configured ALLOWED_USER_IDS: {ALLOWED_USER_IDS}")

    # Initialize managers and store them in bot_data
    # This makes them accessible from handlers via context.application.bot_data
    application.bot_data["task_processor"] = TaskProcessor(REPO_PATH, GH_TOKEN, TARGET_ENVIRONMENT)
    application.bot_data["project_manager"] = ProjectManager(DATA_DIR)
    # Pass application instance for ReminderManager to send messages
    application.bot_data["reminder_manager"] = ReminderManager(DATA_DIR, application) 
    
    # Initialize ObsidianManager conditionally
    if OBSIDIAN_VAULT_PATH:
        obsidian_vault_path_obj = Path(OBSIDIAN_VAULT_PATH)
        if obsidian_vault_path_obj.is_dir():
            application.bot_data["obsidian_manager"] = ObsidianManager(OBSIDIAN_VAULT_PATH)
            log.info(f"ObsidianManager initialized with vault path: {OBSIDIAN_VAULT_PATH}")
        else:
            log.warning(f"OBSIDIAN_VAULT_PATH '{OBSIDIAN_VAULT_PATH}' provided but does not exist or is not a directory. Obsidian integration disabled.")
            application.bot_data["obsidian_manager"] = None
    else:
        log.info("OBSIDIAN_VAULT_PATH not provided. Obsidian integration disabled.")
        application.bot_data["obsidian_manager"] = None
    
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
    
    # Run the bot until the user presses Ctrl-C or the process receives SIGINT, SIGTERM or SIGABRT
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
