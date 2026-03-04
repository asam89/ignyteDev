--- a/README.md
+++ b/README.md
@@ -28,6 +28,11 @@
 Create a Fine-grained Personal Access Token with:
 - Repository access: `asam89/ignyteDev` (and any target repos)
 - Permissions: Contents (read/write), Pull requests (read/write), Metadata (read)
+
+### 4. Environment Variables
+Create a `.env` file in the root of the `ignyteDev` directory with the following:
+- `GEMINI_API_KEY`: Your Google Gemini Pro API key.
+- `GH_TOKEN`: Your GitHub Personal Access Token.
+- `TELEGRAM_TOKEN`: Your Telegram Bot API token.
+- `ALLOWED_USER_IDS`: Comma-separated list of Telegram user IDs authorized to use the bot (e.g., `123456789,987654321`).
+- `OBSIDIAN_VAULT_PATH`: (Optional) Absolute path to your Obsidian vault directory on the host, mounted into the container. E.g., `/path/to/my/ObsidianVault`.
+- `BOT_DATA_DIR`: (Optional) Directory inside the container where bot data (projects, reminders) will be stored. Defaults to `/app/data`.
 
 ## OCI Ampere Server Setup
 
@@ -48,3 +53,4 @@
 cd ~/ignyteDev
 
 # Clone the TARGET repo the bot will write to
+git clone htt
