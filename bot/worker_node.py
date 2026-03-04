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
OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "/obsidian_vault") # New config for Obsidian

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
    application.add_handler(CommandHandler("help", help_command))
    
    # Register /task handler
    application.add_handler(CommandHandler("task", task_command))

    # Register new handlers for project, reminder, obsidian
    application.add_handler(CommandHandler("project", project_command))
    application.add_handler(CommandHandler("remind", remind_command))
    # application.add_handler(CommandHandler("obsidian", obsidian_command)) # To be added later

    # Handle all other messages (optional)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    log.info("Bot is polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# ── Basic Telegram Commands (kept here for simplicity) ────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    if not auth_check(user.id):
        await restricted_access(update, context)
        return

    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm your autonomous development bot. "
        "Send me a `/task` to generate code and open a PR.",
    )
    log.info(f"User {user.id} started the bot.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user = update.effective_user
    if not auth_check(user.id):
        await restricted_access(update, context)
        return

    help_text = """
I'm IgnyteDev, your autonomous development bot! Here's what I can do:

*   `/task <description>`: Describe a coding task, and I'll generate the code, push a branch, and open a PR.
*   `/project <action> [args]`: Manage projects (e.g., `create`, `list`, `get`).
*   `/remind YYYY-MM-DD HH:MM <message>`: Set a reminder message.
*   `/start`: Start interacting with the bot.
*   `/help`: Show this help message.
"""
    await update.message.reply_text(help_text)
    log.info(f"User {user.id} requested help.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    user = update.effective_user
    if not auth_check(user.id):
        await restricted_access(update, context)
        return
        
    await update.message.reply_text(update.message.text)


if __name__ == "__main__":
    main()
