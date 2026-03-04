import os
import json
import subprocess
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── Config ──────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GH_TOKEN = os.environ["GH_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ALLOWED_USER_IDS = [int(uid) for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",") if uid]
REPO_PATH = os.environ.get("REPO_PATH", "/repo")
TARGET_ENVIRONMENT = os.environ.get("TARGET_ENV", "dev")  # "dev" or "prod"
OBSIDIAN_VAULT_NAME = os.environ.get("OBSIDIAN_VAULT_NAME") # Optional: for Obsidian URI generation

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Gemini Setup ────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# ── Helpers ─────────────────────────────────────────────

def auth_check(user_id: int) -> bool:
    """Only allow whitelisted Telegram user IDs."""
    if not ALLOWED_USER_IDS:
        return True  # No whitelist = open (not recommended for prod)
    return user_id in ALLOWED_USER_IDS


def run_git(cmd: str, cwd: str = REPO_PATH) -> str:
    """Run a git command and return output."""
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git error: {result.stderr.strip()}")
    return result.stdout.strip()


def read_repo_context(max_files: int = 20) -> str:
    """Read key files from the repo to give Gemini context."""
    context_parts = []
    repo = Path(REPO_PATH)

    # Always include these if they exist
    priority_files = [
        "README.md", "requirements.txt", "setup.py", "pyproject.toml",
        "Dockerfile", "docker-compose.yml",
    ]

    for fname in priority_files:
        fpath = repo / fname
        if fpath.exists():
            content = fpath.read_text(errors="replace")[:2000]
            context_parts.append(f"--- {fname} ---\n{content}")

    # Scan Python files
    py_files = sorted(repo.rglob("*.py"))[:max_files]
    for fpath in py_files:
        rel = fpath.relative_to(repo)
        if ".git" in str(rel) or "__pycache__" in str(rel):
            continue
        content = fpath.read_text(errors="replace")[:3000]
        context_parts.append(f"--- {rel} ---\n{content}")

    return "\n\n".join(context_parts) if context_parts else "(empty repo)"


def generate_branch_name(task: str) -> str:
    """Create a branch name from the task description."""
    slug = task.lower()[:40]
    slug = "".join(c if c.isalnum() or c == ' ' else '' for c in slug)
    slug = slug.strip().replace(' ', '-')
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"devbot/{slug}-{timestamp}"


async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task commands: send task to Gemini, apply changes, open PR."""
    user_id = update.effective_user.id
    if not auth_check(user_id):
        log.warning(f"Unauthorized user_id: {user_id}")
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    task_description = context.args[0] if context.args else None
    if not task_description:
        await update.message.reply_text("Please provide a task description, e.g., `/task Add a new feature`")
        return

    log.info(f"Received task from user {user_id}: {task_description}")
    await update.message.reply_text("Task received. Generating code, please wait... ⏳")

    try:
        # 1. Read repository context
        log.info("Reading repository context...")
        repo_context = read_repo_context()

        # 2. Generate code and PR details with Gemini
        log.info("Sending task to Gemini Pro...")
        prompt = (
            f"You are an autonomous developer bot. Produce exact file changes for the task.\n"
            f"RESPOND ONLY WITH VALID JSON:\n"
            f"{{"files": [{{"path": "file.py", "action": "create or modify or delete", "content": "full content"}}], "commit_message": "msg", "pr_description": "desc"}}\n\n"
            f"-- Codebase --\n{repo_context}\n\n"
            f"-- Task --\n{task_description}"
        )

        response = model.generate_content(prompt)
        raw_json_response = response.text.strip().replace('```json\n', '').replace('\n```', '')
        parsed_response = json.loads(raw_json_response)

        files_to_change = parsed_response["files"]
        commit_message = parsed_response["commit_message"]
        pr_description = parsed_response["pr_description"]

        # 3. Git operations
        log.info("Starting Git operations...")
        run_git("git checkout main", cwd=REPO_PATH)  # Ensure on main branch
        run_git("git pull origin main", cwd=REPO_PATH)  # Pull latest

        branch_name = generate_branch_name(task_description)
        run_git(f"git checkout -b {branch_name}", cwd=REPO_PATH)

        for file_change in files_to_change:
            path = Path(REPO_PATH) / file_change["path"]
            action = file_change["action"]
            content = file_change.get("content", "")

            if action == "create" or action == "modify":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                log.info(f"Created/Modified: {path}")
            elif action == "delete":
                if path.exists():
                    path.unlink()
                    log.info(f"Deleted: {path}")
                else:
                    log.warning(f"Attempted to delete non-existent file: {path}")
            else:
                log.warning(f"Unknown action '{action}' for file: {path}")
            run_git(f"git add {path.relative_to(REPO_PATH)}", cwd=REPO_PATH)

        run_git(f"git commit -m '{commit_message}'", cwd=REPO_PATH)
        run_git(f"git push -u origin {branch_name}", cwd=REPO_PATH)

        # 4. Create GitHub PR
        log.info("Creating GitHub PR...")
        # gh cli needs token to be available, it's configured in Dockerfile globally
        # However, for robustness, ensure gh is authenticated.
        # The gh auth login command handles this. Assuming it's done during setup.
        pr_command = (
            f"gh pr create --title '{commit_message}' "
            f"--body '{pr_description}' "
            f"--head '{branch_name}' "
            f"--base 'main' "
            f"--repo '{os.environ.get("GITHUB_REPO_OWNER_SLASH_NAME", "")}' " # This assumes a new env var for repo
            f"--json url"
        )
        # Note: The gh cli requires the repo owner/name. Need to update this or assume gh is run from inside the repo
        # For now, let's simplify and assume the gh cli context is correctly set up (i.e., run from /repo)
        # A safer approach would be to pass the full repo name, which is missing here. 
        # Re-evaluating: run_git is called with cwd=REPO_PATH, so gh cli should infer the repo.
        
        # Temporarily adding gh auth setup here for robustness if not already done outside
        run_git(f"gh auth setup-git -p https -h github.com", cwd=REPO_PATH)
        run_git(f"echo '{GH_TOKEN}' | gh auth login --with-token", cwd=REPO_PATH) # Re-authenticate just in case
        
        pr_output = run_git(
            f"gh pr create --title '{commit_message}' --body '{pr_description}' --head '{branch_name}' --base 'main' --json url",
            cwd=REPO_PATH
        )
        pr_url = json.loads(pr_output)["url"]

        log.info(f"PR opened: {pr_url}")
        await update.message.reply_text(f"PR opened: {pr_url}")

        if OBSIDIAN_VAULT_NAME:
            note_title = f"DevBot PR: {commit_message}"
            note_content = (
                f"# {task_description}\n\n"
                f"**GitHub PR:** [{pr_url}]({pr_url})\n"
                f"**Branch:** `{branch_name}`\n"
                f"**Commit:** `{commit_message}`\n"
                f"**Description:**\n{pr_description}\n\n"
                f"---"
            )
            encoded_title = quote(note_title)
            encoded_content = quote(note_content)
            obsidian_uri = (
                f"obsidian://new?"
                f"vault={quote(OBSIDIAN_VAULT_NAME)}&"
                f"name={encoded_title}&"
                f"content={encoded_content}"
            )
            log.info(f"Generated Obsidian URI: {obsidian_uri}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Obsidian Note URI: {obsidian_uri}\n(Click to create a new note in Obsidian)",
                disable_web_page_preview=True, # Prevent Telegram from showing a large preview
            )

    except RuntimeError as e:
        log.error(f"Git/GitHub error: {e}")
        await update.message.reply_text(f"Error during Git/GitHub operations: {e}")
    except json.JSONDecodeError as e:
        log.error(f"JSON parsing error from Gemini: {e}\nRaw response: {raw_json_response}")
        await update.message.reply_text(f"Error parsing Gemini's response. Please try again or refine the task.")
    except Exception as e:
        log.exception("An unexpected error occurred")
        await update.message.reply_text(f"An unexpected error occurred: {e}")


async def post_init(application: Application) -> None:
    """Post-initialization hook for the bot application."""
    log.info("Bot started successfully.")
    # Attempt to authenticate gh cli at startup, relies on GH_TOKEN env var
    try:
        # Ensure git identity is set, if not already in Dockerfile
        run_git("git config --global user.email 'bot@ignyteconsulting.com'")
        run_git("git config --global user.name 'IgnyteDev Bot'")

        # Authenticate gh CLI. This needs to be done once per container lifespan.
        # This line is crucial for gh commands to work without interactive prompts.
        run_git(f"echo '{GH_TOKEN}' | gh auth login --with-token", cwd=REPO_PATH)
        log.info("GitHub CLI authenticated successfully.")
    except Exception as e:
        log.error(f"Failed to authenticate GitHub CLI at startup: {e}")


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("task", handle_task))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
