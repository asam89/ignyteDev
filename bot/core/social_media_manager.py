import logging
from pathlib import Path
from tinydb import TinyDB, Query
import tweepy

log = logging.getLogger(__name__)

class SocialMediaManager:
    """Manages connections and interactions with social media accounts."""

    def __init__(self, data_dir: Path, x_api_key: str, x_api_secret: str):
        self.data_dir = data_dir
        self.db_path = self.data_dir / "social_accounts.json"
        self.db = TinyDB(self.db_path)
        self.x_api_key = x_api_key
        self.x_api_secret = x_api_secret
        log.info(f"SocialMediaManager initialized, data stored at {self.db_path}")

        if not self.x_api_key or not self.x_api_secret:
            log.warning("X (Twitter) API keys not provided. X integration will be limited.")

    def _get_x_api(self, chat_id: int) -> tweepy.API | None:
        """Helper to get an authenticated Tweepy API object for a given chat_id."""
        Account = Query()
        user_account = self.db.get((Account.platform == 'x') & (Account.chat_id == chat_id))

        if not user_account:
            log.warning(f"No X account found for chat_id {chat_id}")
            return None

        access_token = user_account.get('access_token')
        access_token_secret = user_account.get('access_token_secret')

        if not access_token or not access_token_secret:
            log.error(f"X access tokens missing for chat_id {chat_id}")
            return None

        try:
            auth = tweepy.OAuthHandler(self.x_api_key, self.x_api_secret)
            auth.set_access_token(access_token, access_token_secret)
            api = tweepy.API(auth)
            # Verify credentials to ensure tokens are valid
            api.verify_credentials()
            log.info(f"X API client created for chat_id {chat_id}")
            return api
        except tweepy.TweepyException as e:
            log.error(f"Failed to create X API client for chat_id {chat_id}: {e}")
            return None

    def connect_x(self, chat_id: int, access_token: str, access_token_secret: str) -> bool:
        """Stores X (Twitter) access tokens for a user/chat_id.
        NOTE: For a production bot, this process should ideally involve an OAuth web flow,
        not direct input of tokens, for security reasons.
        """
        if not self.x_api_key or not self.x_api_secret:
            log.error("Cannot connect X: Bot's X API keys are not configured.")
            return False

        Account = Query()
        existing = self.db.get((Account.platform == 'x') & (Account.chat_id == chat_id))

        data = {
            "platform": "x",
            "chat_id": chat_id,
            "access_token": access_token,
            "access_token_secret": access_token_secret
        }

        if existing:
            self.db.update(data, doc_ids=[existing.doc_id])
            log.info(f"Updated X account for chat_id {chat_id}")
        else:
            self.db.insert(data)
            log.info(f"Connected X account for chat_id {chat_id}")
        return True

    async def post_x(self, chat_id: int, message: str) -> str:
        """Posts a tweet to X (Twitter) using the connected account for the chat_id."""
        api = self._get_x_api(chat_id)
        if not api:
            return "X account not connected or credentials invalid for this chat. Please use `/social connect x <access_token> <access_token_secret>` first."

        try:
            api.update_status(message)
            log.info(f"Successfully tweeted from chat_id {chat_id}")
            return "✅ Tweet posted successfully!"
        except tweepy.TweepyException as e:
            log.error(f"Failed to post tweet from chat_id {chat_id}: {e}")
            return f"Failed to post tweet: {e}"

    # Placeholder for LinkedIn integration
    def connect_linkedin(self, chat_id: int, auth_details: dict) -> bool:
        log.info(f"Attempting to connect LinkedIn for chat_id {chat_id}")
        # In a real scenario, this would involve OAuth 2.0 flow and storing tokens.
        return False

    async def post_linkedin(self, chat_id: int, message: str) -> str:
        log.info(f"Attempting to post to LinkedIn for chat_id {chat_id}")
        return "LinkedIn integration is not yet implemented."

    # Placeholder for Instagram integration
    def connect_instagram(self, chat_id: int, auth_details: dict) -> bool:
        log.info(f"Attempting to connect Instagram for chat_id {chat_id}")
        # Instagram API is restricted; often requires business accounts or specialized tools.
        return False

    async def post_instagram(self, chat_id: int, image_url: str, caption: str) -> str:
        log.info(f"Attempting to post to Instagram for chat_id {chat_id}")
        return "Instagram integration is not yet implemented and complex for bots."
