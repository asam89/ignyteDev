import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import auth_check, restricted_access, get_managers
from bot.core.social_media_manager import SocialMediaManager

log = logging.getLogger(__name__)

async def social_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /social command for connecting/posting to social media."""
    user_id = update.effective_user.id
    if not auth_check(user_id):
        await restricted_access(update, context)
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/social <action> <platform> [args]`\n" +
            "Actions: `connect`, `post`\n" +
            "Platforms: `x` (Twitter), `linkedin`, `instagram`\n" +
            "Example: `/social connect x <access_token> <access_token_secret>`\n" +
            "Example: `/social post x This is a tweet from my bot!`"
        )
        return

    managers = get_managers(context)
    social_media_manager: SocialMediaManager = managers.get("social_media_manager")
    if not social_media_manager:
        await update.message.reply_text("Social Media manager not initialized. Please check bot configuration.")
        return

    action = context.args[0].lower()
    platform = context.args[1].lower() if len(context.args) > 1 else None
    chat_id = update.effective_chat.id

    if action == "connect":
        if platform == "x":
            if len(context.args) < 4:
                await update.message.reply_text(
                    "Usage: `/social connect x <access_token> <access_token_secret>`\n" +
                    "*WARNING*: Providing tokens directly in chat is insecure. This is for demonstration only.\n" +
                    "A production bot would use an OAuth web flow."
                )
                return
            access_token = context.args[2]
            access_token_secret = context.args[3]
            
            if social_media_manager.connect_x(chat_id, access_token, access_token_secret):
                await update.message.reply_text("✅ X (Twitter) account connected!")
            else:
                await update.message.reply_text("❌ Failed to connect X (Twitter) account. Check bot's API keys or provided tokens.")

        elif platform == "linkedin":
            await update.message.reply_text("LinkedIn connection is not yet implemented. Imagine an OAuth flow here.")
        elif platform == "instagram":
            await update.message.reply_text("Instagram connection is not yet implemented and often requires business APIs.")
        else:
            await update.message.reply_text(f"Unknown platform for connect: {platform}")

    elif action == "post":
        if platform == "x":
            if len(context.args) < 3:
                await update.message.reply_text("Usage: `/social post x <message>`")
                return
            message = " ".join(context.args[2:])
            response = await social_media_manager.post_x(chat_id, message)
            await update.message.reply_text(response, parse_mode="Markdown")

        elif platform == "linkedin":
            await update.message.reply_text("LinkedIn posting is not yet implemented.")
        elif platform == "instagram":
            await update.message.reply_text("Instagram posting is not yet implemented.")
        else:
            await update.message.reply_text(f"Unknown platform for post: {platform}")

    else:
        await update.message.reply_text(f"Unknown social media action: {action}. Use `connect` or `post`.")
