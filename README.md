# IgnyteDev - Autonomous Development Bot

Telegram-driven autonomous dev bot running on OCI Ampere, powered by Gemini Pro.
Send a `/task` via Telegram -> Gemini generates code -> bot pushes a branch and opens a PR on GitHub.

## Architecture

```
Telegram -> Bot (OCI Ampere/Docker) -> Gemini Pro API -> GitHub PR
                                                          |
                                                GitHub Actions Pipeline
                                                dev/** -> Development
                                                main   -> Production (requires approval)
```

## Repo Setup (GitHub UI)

### 1. Create Environments
- Settings -> Environments -> New environment
- Create `development` (no restrictions)
- Create `production` -> enable Required reviewers -> add yourself

### 2. Branch Protection
- Settings -> Branches -> Add ruleset for `main`
- Enable Require a pull request before merging
- Enable Require approvals (1 reviewer minimum)
- Optionally enable Require status checks -> select `lint-and-test`

### 3. GitHub Token
Create a Fine-grained Personal Access Token with:
- Repository access: `asam89/ignyteDev` (and any target repos)
- Permissions: Contents (read/write), Pull requests (read/write), Metadata (read)

## OCI Ampere Server Setup

```bash
ssh ubuntu@<your-oci-ip>

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
  https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh -y

gh auth login

git clone https://github.com/asam89/ignyteDev.git ~/ignyteDev
cd ~/ignyteDev

# Clone the TARGET repo the bot will write to
git clone htt
```

### Bot Configuration

Create a `.env` file in the root of the `ignyteDev` directory with the following variables:

```
# Required
GEMINI_API_KEY="your_gemini_api_key"
GH_TOKEN="your_github_token"
TELEGRAM_TOKEN="your_telegram_bot_token"
ALLOWED_USER_IDS="123456789,987654321" # Comma-separated list of Telegram user IDs

# Optional
OBSIDIAN_VAULT_NAME="Your Obsidian Vault Name" # If set, bot will provide an obsidian:// URI for new PRs.
```
