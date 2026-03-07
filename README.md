--- a/README.md
+++ b/README.md
@@ -31,6 +31,10 @@
 - `ALLOWED_USER_IDS`: Comma-separated list of Telegram user IDs authorized to use the bot (e.g., `123456789,987654321`).
 - `OBSIDIAN_VAULT_PATH`: (Optional) Absolute path to your Obsidian vault directory on the host, mounted into the container. E.g., `/path/to/my/ObsidianVault`.
 - `BOT_DATA_DIR`: (Optional) Directory inside the container where bot data (projects, reminders) will be stored. Defaults to `/app/data`.
+
+For social media integration (e.g., X/Twitter):
+- `X_API_KEY`: Your X (Twitter) API Consumer Key.
+- `X_API_SECRET`: Your X (Twitter) API Consumer Secret.
 
 ## OCI Ampere Server Setup
 
