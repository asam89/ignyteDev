# IgnyteDev — Autonomous Development Bot

AI-powered development bot with a **web dashboard** and **Telegram** interface. Submit feature requirements (with file uploads), and the bot generates code, pushes branches, and opens PRs — using **Claude** and/or **Gemini**.

## Architecture

```
Web Dashboard (FastAPI + HTMX)  ─┐
                                  ├─→ Task Queue → LLM (Claude/Gemini) → Code → PR
Telegram Bot                    ─┘
```

**Components:**
- `dashboard/` — Web UI for task submission, queue monitoring, fleet status
- `bot/` — Telegram bot + core logic (task processor, LLM, git utils)
- `docker-compose.yml` — Runs dashboard, bot, and Caddy reverse proxy

## Quick Start

### 1. Clone and configure
```bash
git clone https://github.com/asam89/ignyteDev.git
cd ignyteDev
cp .env.example .env
# Fill in API keys in .env
```

### 2. Run with Docker Compose
```bash
docker compose up -d
```

The web dashboard will be available at `http://localhost:8080`.

### 3. Environment Variables

Create a `.env` file (see `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | At least one LLM key | Google Gemini API key |
| `ANTHROPIC_API_KEY` | At least one LLM key | Anthropic Claude API key |
| `GH_TOKEN` | Yes | GitHub PAT with repo + PR permissions |
| `TELEGRAM_TOKEN` | For Telegram bot | Telegram Bot API token |
| `ALLOWED_USER_IDS` | For Telegram bot | Comma-separated Telegram user IDs |
| `REPO_PATH` | No | Default target repo path (default: `/repo`) |
| `REPOS_DIR` | No | Directory for cloned repos (default: `/repos`) |
| `TARGET_ENV` | No | `dev` or `prod` (default: `dev`) |

### 4. GitHub Token

Create a [Fine-grained Personal Access Token](https://github.com/settings/tokens?type=beta) with:
- Repository access: `asam89/ignyteDev` (and any target repos)
- Permissions: Contents (read/write), Pull requests (read/write), Metadata (read)

## Web Dashboard

The dashboard at `:8080` lets you:
- **Submit tasks** with descriptions and file uploads (PDFs, markdown, code)
- **Target any GitHub repo** — not just the default mounted one
- **Choose LLM provider** — Claude, Gemini, or auto (tries Claude first)
- **Monitor task queue** — see pending, building, completed, and failed tasks
- **View PR results** — direct links to opened pull requests

Tasks auto-refresh via HTMX polling.

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/task <description>` | Submit a coding task |
| `/project create\|list\|get` | Manage projects |
| `/remind YYYY-MM-DD HH:MM <msg>` | Set a reminder |
| `/help` | Show available commands |

## OCI Ampere Deployment

### GitHub Actions CI/CD

The pipeline (`.github/workflows/pipeline.yml`) handles:
- **Lint + Test** on every push/PR
- **Deploy to Dev** on `dev/**` branches (via SSH)
- **Deploy to Prod** on `main` push (via SSH)

Add these secrets to [repo settings](https://github.com/asam89/ignyteDev/settings/secrets/actions):

| Secret | Value |
|--------|-------|
| `OCI_HOST` | IP/hostname of OCI instance |
| `OCI_USER` | SSH username (likely `ubuntu`) |
| `OCI_SSH_KEY` | Private SSH key for the instance |

### Manual Setup

```bash
ssh ubuntu@YOUR_OCI_IP

# Clone
git clone https://github.com/asam89/ignyteDev.git ~/ignyteDev
cd ~/ignyteDev

# Configure
cp .env.example .env
nano .env  # Fill in API keys

# Run
docker compose up -d

# Verify
curl http://localhost:8080
```

## Multi-Repo Support

The task processor can target **any GitHub repo**:
1. Via the web dashboard: paste the repo URL in the "Target Repo" field
2. The bot clones the repo, reads its context, generates changes, and opens a PR
3. Repos are cached in `/repos/` for subsequent tasks

## Development

```bash
# Run dashboard locally (without Docker)
pip install -r requirements.txt
uvicorn dashboard.app:app --reload --port 8080

# Run Telegram bot locally
python bot/worker_node.py

# Run tests
pytest tests/ -v

# Lint
flake8 . --select=E9,F63,F7,F82
```
