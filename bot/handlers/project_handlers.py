import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import auth_check, restricted_access, get_managers
from bot.core.project_manager import ProjectManager

log = logging.getLogger(__name__)

async def project_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /project command for project management."""
    user_id = update.effective_user.id
    if not auth_check(user_id):
        await restricted_access(update, context)
        return

    if not context.args:
        await update.message.reply_text(
            "Please specify a project action: `/project create <name> [description]`, `/project list`, `/project get <name>`"
        )
        return

    managers = get_managers(context)
    project_manager: ProjectManager = managers.get("project_manager")
    if not project_manager:
        await update.message.reply_text("Project manager not initialized. Please check bot configuration.")
        return

    action = context.args[0].lower()

    try:
        if action == "create":
            if len(context.args) < 2:
                await update.message.reply_text("Usage: `/project create <name> [description]`")
                return
            name = context.args[1]
            description = " ".join(context.args[2:]) if len(context.args) > 2 else ""
            project = project_manager.create_project(name, description)
            await update.message.reply_text(f"✅ Project '{project['name']}' created!")

        elif action == "list":
            projects = project_manager.list_projects()
            if not projects:
                await update.message.reply_text("No projects found.")
                return
            
            response = "📊 **Current Projects:**\n"
            for p in projects:
                response += f"- **{p['name']}** ({p.get('status', 'N/A')}): {p.get('description', 'No description')}\n"
            await update.message.reply_text(response, parse_mode="Markdown")

        elif action == "get":
            if len(context.args) < 2:
                await update.message.reply_text("Usage: `/project get <name>`")
                return
            name = context.args[1]
            project = project_manager.get_project(name)
            if project:
                await update.message.reply_text(f"Project Details for '{name}': {project}")
            else:
                await update.message.reply_text(f"Project '{name}' not found.")

        else:
            await update.message.reply_text(
                f"Unknown project action: '{action}'. Use `create`, `list`, or `get`."
            )

    except Exception as e:
        log.exception(f"Error handling project command: {e}")
        await update.message.reply_text(f"An error occurred while processing the project command: {e}")
