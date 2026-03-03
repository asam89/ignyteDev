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
git clone https://github.com/asam89/YOUR_TARGET_REPO.git ~/ignyteDev/repo

git config --global user.email "alex@ignyteconsulting.com"
git config --global user.name "IgnyteDev Bot"
```

## Deploy

```bash
cd ~/ignyteDev
cp .env.example .env
nano .env

docker compose up -d --build
docker compose logs -f
```

## Usage

1. Open Telegram -> find your bot
2. `/start` - verify bot is alive
3. `/status` - check repo and branch info
4. `/files` - list tracked files
5. `/task add a hello world function to utils.py` - bot generates code, pushes branch, opens PR

## Workflow

| Branch pattern | Environment | Auto-deploy? |
|----------------|-------------|--------------|
| `dev/*`        | development | Yes          |
| `feature/*`    | -           | Lint/test only |
| `main`         | production  | Requires approval |

The bot pushes to `dev/` branches by default (`TARGET_ENV=dev`).
Merging a PR to `main` triggers the production pipeline with required reviewer approval.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `GH_TOKEN` | GitHub PAT with repo + PR permissions |
| `TELEGRAM_TOKEN` | Bot token from BotFather |
| `ALLOWED_USER_IDS` | Comma-separated Telegram user IDs |
| `REPO_PATH` | Path to mounted target repo (default: `/repo`) |
| `TARGET_ENV` | `dev` or `prod` - controls branch prefix |
