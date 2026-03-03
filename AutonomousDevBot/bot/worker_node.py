"""
Autonomous Dev Node — Worker
Telegram Bot → Gemini Pro API → GitHub PR

Runs on OCI Ampere instance inside Docker.
Listens for /task commands, generates code with Gemini, pushes branches, opens PRs.
"""

import os
import json
import subprocess
import logging
import asyncio
from pathlib import Path
from datetime import datetime

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
    slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
    ts = datetime.utcnow().strftime("%m%d%H%M")
    prefix = "dev" if TARGET_ENVIRONMENT == "dev" else "feature"
    return f"{prefix}/{slug}-{ts}"


# ── Core Logic ──────────────────────────────────────────

async def process_task(task: str) -> dict:
    """
    1. Read repo context
    2. Ask Gemini to generate code changes
    3. Apply changes, commit, push branch
    4. Open a PR via GitHub CLI
    """
    log.info(f"Processing task: {task}")

    # 1 — Read repo
    repo_context = read_repo_context()

    # 2 — Ask Gemini
    prompt = f"""You are an autonomous developer bot. You are given a codebase and a task.
Your job is to produce the exact file changes needed to accomplish the task.

RESPOND ONLY WITH VALID JSON in this format:
{{
  "files": [
    {{
      "path": "relative/path/to/file.py",
      "action": "create" | "modify" | "delete",
      "content": "full file content (for create/modify)"
    }}
  ],
  "commit_message": "short commit message",
  "pr_description": "description of changes for the pull request"
}}

── Current Codebase ──
{repo_context}

── Task ──
{task}
"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    changes = json.loads(raw)
    log.info(f"Gemini proposed {len(changes['files'])} file change(s)")

    # 3 — Apply changes
    branch = generate_branch_name(task)
    run_git("git fetch origin")
    run_git(f"git checkout -b {branch} origin/main")

    for file_change in changes["files"]:
        fpath = Path(REPO_PATH) / file_change["path"]

        if file_change["action"] == "delete":
            if fpath.exists():
                fpath.unlink()
                run_git(f"git rm {file_change['path']}")
        else:
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(file_change["content"])
            run_git(f"git add {file_change['path']}")

    run_git(f'git commit -m "{changes["commit_message"]}"')
    run_git(f"git push origin {branch}")

    # 4 — Open PR
    base = "main"
    pr_title = changes["commit_message"]
    pr_body = changes.get("pr_description", task)
    pr_output = run_git(
        f'gh pr create --base {base} --head {branch} '
        f'--title "{pr_title}" --body "{pr_body}"'
    )

    # Clean up — go back to main
    run_git("git checkout main")

    return {
        "branch": branch,
        "files_changed": len(changes["files"]),
        "pr": pr_output,
        "commit_message": changes["commit_message"],
    }


# ── Telegram Handlers ──────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    await update.message.reply_text(
        "🤖 Autonomous Dev Node awake.\n\n"
        f"📂 Repo: {REPO_PATH}\n"
        f"🌿 Target env: {TARGET_ENVIRONMENT}\n\n"
        "Commands:\n"
        "/task <description> — generate code & open PR\n"
        "/status — check bot health\n"
        "/files — list repo files"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update.effective_user.id):
        return
    try:
        branch = run_git("git branch --show-current")
        last_commit = run_git("git log -1 --oneline")
        await update.message.reply_text(
            f"✅ Bot is healthy\n"
            f"📂 Repo: {REPO_PATH}\n"
            f"🌿 Branch: {branch}\n"
            f"📝 Last commit: {last_commit}\n"
            f"🎯 Environment: {TARGET_ENVIRONMENT}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update.effective_user.id):
        return
    try:
        tree = run_git("git ls-files")
        files = tree.split("\n")[:30]
        msg = "📂 Repo files:\n" + "\n".join(f"  • {f}" for f in files)
        if len(tree.split("\n")) > 30:
            msg += f"\n  ... and {len(tree.split(chr(10))) - 30} more"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_check(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    task = " ".join(context.args) if context.args else ""
    if not task:
        await update.message.reply_text("Usage: /task <describe what you want built>")
        return

    await update.message.reply_text(f"🔄 Working on: {task}\n\nThis may take a minute...")

    try:
        result = await asyncio.to_thread(process_task, task)
        await update.message.reply_text(
            f"✅ Done!\n\n"
            f"🌿 Branch: `{result['branch']}`\n"
            f"📝 {result['files_changed']} file(s) changed\n"
            f"💬 {result['commit_message']}\n"
            f"🔗 PR: {result['pr']}",
            parse_mode="Markdown",
        )
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Gemini returned invalid JSON. Try rephrasing your task.")
    except Exception as e:
        log.exception("Task failed")
        await update.message.reply_text(f"❌ Failed: {e}")


# ── Main ────────────────────────────────────────────────

def main():
    log.info("Starting Autonomous Dev Node...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("files", cmd_files))
    app.add_handler(CommandHandler("task", cmd_task))

    log.info("Bot is polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
