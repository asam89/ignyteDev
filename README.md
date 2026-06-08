# IgnyteDev

**Autonomous AI development platform.** Submit feature requirements through a web dashboard or Telegram, and AI agents generate code, push branches, open PRs, and deploy live previews — all without human intervention.

Built for solo developers and small teams who want to move fast: describe what you want, attach reference docs, and let the bot build it.

---

## Vision

IgnyteDev is part of a three-repo ecosystem designed to run an autonomous AI-powered development and operations fleet on a single OCI Ampere (ARM64) instance:

| Repo | Role |
|------|------|
| **[ignyteDev](https://github.com/asam89/ignyteDev)** | Core dev bot — takes requirements, generates code, opens PRs, deploys previews |
| **[solo-agent-fleet](https://github.com/asam89/solo-agent-fleet)** | Operational agent fleet — career, content, business, and ops agents on systemd timers |
| **[presence-agent](https://github.com/asam89/presence-agent)** | Daily presence logging (now also integrated into the fleet) |

The long-term goal: a self-improving development loop where you feed requirements into a UI, AI builds the features, preview containers let you verify the output, and the cycle continues — constantly building and improving your projects.

---

## How It Works

```
                  ┌─────────────────────┐
                  │   Web Dashboard     │
                  │   (FastAPI + HTMX)  │
                  │                     │
                  │  - Submit tasks     │
                  │  - Upload files     │
                  │  - Connect projects │
                  │  - Build previews   │
                  └────────┬────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
     ┌─────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐
     │  Telegram  │  │   Task    │  │  Connected  │
     │    Bot     │  │   Queue   │  │  Projects   │
     │  (mobile)  │  │ (TinyDB)  │  │  Registry   │
     └─────┬──────┘  └─────┬─────┘  └──────┬──────┘
           │               │               │
           └───────┬───────┘               │
                   │                       │
            ┌──────▼───────┐        ┌──────▼──────┐
            │     LLM      │        │   Preview   │
            │  Claude /    │        │  Deployer   │
            │  Gemini      │        │  (Docker)   │
            └──────┬───────┘        └──────┬──────┘
                   │                       │
            ┌──────▼───────┐        ┌──────▼──────┐
            │  Git: branch │        │  Container  │
            │  commit,push │        │  at :9000+  │
            │  open PR     │        │             │
            └──────────────┘        └─────────────┘
```

1. **Submit a task** — via the web dashboard (with file uploads) or Telegram (`/task`)
2. **AI generates code** — Claude or Gemini reads the repo context + your requirements, produces file changes as structured JSON
3. **Bot commits and opens a PR** — creates a branch, applies changes, pushes, and opens a pull request
4. **Preview deployment** — for connected projects, the bot builds a Docker container and serves a live preview

---

## Features

### Web Dashboard (`:8080`)
- **Task submission** with descriptions and file uploads (PDFs, markdown, code, images)
- **Target any GitHub repo** — paste a URL, the bot clones and targets it
- **LLM provider selector** — Claude, Gemini, or auto (tries Claude first, falls back to Gemini)
- **Task queue** with live status updates via HTMX polling (pending / building / completed / failed)
- **Direct PR links** for every completed task

### Connected Projects
- **Persistent project registry** — link GitHub repos as ongoing projects
- **Project-scoped tasks** — submit requirements from within a project page
- **Docker preview deployments** — one-click "Build & Deploy Preview" per project
- **Auto-framework detection** — generates appropriate Dockerfiles for Next.js, React, Vue, Express, FastAPI, Flask, Django, and static HTML
- **Preview URLs** at `http://<host>:9000+` per project
- **Task history per project** — see all PRs opened for that project

### Dual LLM Support
- **Claude** (`claude-sonnet-4-20250514`) — primary provider
- **Gemini** (`gemini-2.5-flash-preview-05-20`) — secondary / fallback
- **Auto mode** — tries Claude first; if it fails, falls back to Gemini
- Configure one or both via API keys

### Telegram Bot
- `/task <description>` — submit a coding task
- `/project create|list|get` — manage projects
- `/remind YYYY-MM-DD HH:MM <message>` — set a reminder
- `/help` — show available commands
- File upload support for requirement documents

### CI/CD Pipeline
- **Lint + Test** on every push and PR
- **Auto-deploy to dev** on `dev/**` branches via SSH
- **Auto-deploy to production** on push to `main` via SSH
- Uses `appleboy/ssh-action` to SSH into OCI and run `docker compose`

---

## Architecture

```
ignyteDev/
├── bot/                          # Telegram bot + core logic
│   ├── worker_node.py            # Bot entrypoint
│   ├── handlers/                 # Telegram command handlers
│   │   ├── task_handlers.py      # /task command
│   │   ├── project_handlers.py   # /project command
│   │   ├── reminder_handlers.py  # /remind command
│   │   └── common.py             # /start, /help
│   └── core/                     # Shared business logic
│       ├── llm.py                # Dual LLM wrapper (Claude + Gemini)
│       ├── task_processor.py     # Code generation + PR pipeline
│       ├── task_queue.py         # Async task queue with TinyDB persistence
│       ├── project_registry.py   # Connected projects store
│       ├── preview_deployer.py   # Docker preview build/run
│       ├── repo_reader.py        # Reads repo structure for LLM context
│       └── git_utils.py          # Git CLI wrappers
├── dashboard/                    # Web UI
│   ├── app.py                    # FastAPI application
│   ├── templates/                # Jinja2 + HTMX templates
│   │   ├── base.html             # Layout with nav
│   │   ├── index.html            # Home — task form + queue + stats
│   │   ├── tasks.html            # Task list with filters
│   │   ├── task_detail.html      # Single task view
│   │   ├── projects.html         # Connected projects list
│   │   ├── project_detail.html   # Project view with preview controls
│   │   └── partials/             # HTMX live-update fragments
│   └── static/                   # CSS, JS assets
├── docker-compose.yml            # 3 services: bot, dashboard, caddy
├── Dockerfile                    # Python 3.12 + git + gh CLI + Docker CLI
├── Caddyfile                     # Reverse proxy config
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variable template
└── .github/workflows/
    └── pipeline.yml              # CI/CD: lint, test, deploy
```

### Docker Services

| Service | Container | Port | Purpose |
|---------|-----------|------|---------|
| `dev-node` | `ignyte-dev-node` | — | Telegram bot + task worker |
| `dashboard` | `ignyte-dashboard` | `8080` | FastAPI web UI |
| `caddy` | `ignyte-caddy` | `80`, `443` | Reverse proxy, HTTPS |

Preview containers are created dynamically on the `ignyte-previews` Docker network, starting at port `9000`.

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/asam89/ignyteDev.git
cd ignyteDev
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# LLM Providers (at least one required)
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# GitHub — PAT with repo + PR permissions
GH_TOKEN=your_github_personal_access_token_here

# Telegram Bot (optional — only needed for Telegram interface)
TELEGRAM_TOKEN=your_telegram_bot_token_here
ALLOWED_USER_IDS=your_telegram_user_id_here
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

The web dashboard will be available at `http://localhost:8080`.

### 3. Use the dashboard

1. Go to `http://localhost:8080`
2. Enter a task description (e.g., "Add a dark mode toggle to the settings page")
3. Paste the target GitHub repo URL
4. Optionally upload requirement docs (PDFs, markdown, code files)
5. Select LLM provider (Claude, Gemini, or auto)
6. Submit — the bot generates code and opens a PR

### 4. Connect a project

1. Go to `http://localhost:8080/projects`
2. Click "Connect Project"
3. Enter the repo URL and project name
4. Submit tasks from the project page
5. Click "Build & Deploy Preview" to see a live preview

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | At least one LLM key | Google Gemini API key |
| `ANTHROPIC_API_KEY` | At least one LLM key | Anthropic Claude API key |
| `GH_TOKEN` | Yes | GitHub PAT with `repo` + `pull_request` permissions |
| `TELEGRAM_TOKEN` | For Telegram bot | Telegram Bot API token |
| `ALLOWED_USER_IDS` | For Telegram bot | Comma-separated Telegram user IDs |
| `REPO_PATH` | No | Default target repo path (default: `/repo`) |
| `REPOS_DIR` | No | Directory for cloned repos (default: `/repos`) |
| `TARGET_ENV` | No | `dev` or `prod` (default: `dev`) |
| `BOT_DATA_DIR` | No | TinyDB data directory (default: `/app/data`) |
| `UPLOAD_DIR` | No | Upload directory (default: `/app/uploads`) |
| `DASHBOARD_PORT` | No | Dashboard port (default: `8080`) |
| `DOCKER_NETWORK` | No | Preview container network (default: `ignyte-previews`) |
| `PREVIEW_BASE_PORT` | No | Starting port for previews (default: `9000`) |

### GitHub Token

Create a [Fine-grained Personal Access Token](https://github.com/settings/tokens?type=beta) with:
- **Repository access**: All repos you want the bot to target
- **Permissions**: Contents (read/write), Pull requests (read/write), Metadata (read)

---

## OCI Ampere Deployment

IgnyteDev is designed to run on an OCI Ampere A1 always-free tier instance (ARM64). Total cost: ~$3-5/month for LLM API calls only.

### Automated Deployment (GitHub Actions)

The CI/CD pipeline auto-deploys on push to `main`. Add these secrets to [repo settings](https://github.com/asam89/ignyteDev/settings/secrets/actions):

| Secret | Value |
|--------|-------|
| `OCI_HOST` | IP/hostname of OCI instance |
| `OCI_USER` | SSH username (likely `ubuntu`) |
| `OCI_SSH_KEY` | Private SSH key for the instance |

Once configured, every push to `main` will:
1. Run lint and tests
2. SSH into the OCI instance
3. Pull the latest code
4. Rebuild and restart Docker containers

### Manual Deployment

```bash
ssh ubuntu@YOUR_OCI_IP

# Clone (first time)
git clone https://github.com/asam89/ignyteDev.git ~/ignyteDev
cd ~/ignyteDev

# Configure
cp .env.example .env
nano .env  # Fill in API keys

# Start
docker compose up -d

# Verify
curl http://localhost:8080
docker ps
```

The dashboard will be accessible at `http://YOUR_OCI_IP:8080`.

### Port Requirements

Ensure these ports are open in your OCI security list:

| Port | Service |
|------|---------|
| `80` | Caddy (HTTP) |
| `443` | Caddy (HTTPS) |
| `8080` | Dashboard (direct access) |
| `9000+` | Preview containers |

---

## Multi-Repo Support

The bot can target **any GitHub repo**, not just its own:

1. **Via the web dashboard**: Paste the repo URL in the "Target Repo" field when submitting a task
2. **Via connected projects**: Link a repo once, then submit multiple tasks against it
3. The bot clones the repo, reads its structure for LLM context, generates changes, and opens a PR
4. Repos are cached in `/repos/` for subsequent tasks

---

## Preview Deployments

Connected projects can be built and served as Docker containers:

1. **Auto-framework detection** scans the repo for:
   - `next.config.js` / `next.config.mjs` / `next.config.ts` → Next.js
   - `package.json` with `react` → React (served via `serve`)
   - `package.json` with `vue` → Vue
   - `package.json` with `express` → Express
   - `requirements.txt` / `pyproject.toml` with `fastapi` → FastAPI
   - `requirements.txt` / `pyproject.toml` with `flask` → Flask
   - `requirements.txt` / `pyproject.toml` with `django` → Django
   - `index.html` → Static (nginx)

2. **If no Dockerfile exists**, the deployer generates one appropriate for the detected framework

3. **Preview containers** run on the `ignyte-previews` Docker network, accessible at `http://<host>:9000`, `:9001`, etc.

4. **Rebuild on task completion** — check "Rebuild preview after task completes" when submitting a project-scoped task

---

## API Endpoints

### Tasks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard home |
| `GET` | `/tasks` | Task list (filter by `?status=`) |
| `GET` | `/tasks/{id}` | Task detail |
| `POST` | `/api/tasks` | Create task (form: `description`, `repo_url`, `llm_provider`, `files[]`) |
| `GET` | `/api/tasks` | List tasks (JSON) |
| `GET` | `/api/tasks/{id}` | Get task (JSON) |
| `GET` | `/api/stats` | Queue stats (JSON) |

### Projects

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects` | Projects list |
| `GET` | `/projects/{id}` | Project detail with preview controls |
| `POST` | `/api/projects` | Connect project (form: `name`, `repo_url`, `description`, `framework`) |
| `POST` | `/api/projects/{id}/deploy-preview` | Build and deploy preview container |
| `POST` | `/api/projects/{id}/stop-preview` | Stop preview container |
| `GET` | `/api/projects/{id}/logs` | Preview container logs |

### HTMX Partials

| Path | Description |
|------|-------------|
| `/partials/task-rows` | Live task table rows |
| `/partials/stats` | Live dashboard stats |
| `/partials/project-cards` | Live project cards |

---

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

---

## Tech Stack

- **Python 3.12** — core runtime
- **FastAPI** — web framework for the dashboard
- **HTMX** — live updates without JavaScript frameworks
- **Jinja2** — server-side templates
- **TinyDB** — lightweight JSON database for tasks and projects
- **python-telegram-bot** — Telegram interface
- **Anthropic SDK** — Claude API client
- **google-generativeai** — Gemini API client
- **Docker** — containerization for the platform and preview deployments
- **Caddy** — reverse proxy with automatic HTTPS
- **GitHub Actions** — CI/CD pipeline

---

## Related Repos

- **[solo-agent-fleet](https://github.com/asam89/solo-agent-fleet)** — Operational agent fleet with systemd timers for career, content, business, and ops tasks. Shares the same OCI instance.
- **[presence-agent](https://github.com/asam89/presence-agent)** — Daily presence logging agent. Now also integrated into the solo-agent-fleet.

---

## License

Private — Ignyte Consulting
