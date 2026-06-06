"""
IgnyteDev Web Dashboard — FastAPI + HTMX.

Submit tasks, upload requirements, view queue, monitor fleet.
"""

import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from bot.core.task_processor import TaskProcessor
from bot.core.task_queue import TaskQueue
from bot.core.llm import available_providers

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)

# Config
DATA_DIR = Path(os.environ.get("BOT_DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REPO_PATH = os.environ.get("REPO_PATH", "/repo")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
TARGET_ENV = os.environ.get("TARGET_ENV", "dev")

# Dashboard directory (for templates/static)
DASHBOARD_DIR = Path(__file__).parent

# App setup
app = FastAPI(title="IgnyteDev Dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")
templates = Jinja2Templates(directory=DASHBOARD_DIR / "templates")

# Shared state
task_queue = TaskQueue(DATA_DIR)
task_processor = TaskProcessor(REPO_PATH, GH_TOKEN, TARGET_ENV)
task_queue.set_processor(task_processor)


@app.on_event("startup")
async def startup():
    asyncio.create_task(task_queue.run_worker())
    log.info("Dashboard started, task worker running")


@app.on_event("shutdown")
async def shutdown():
    task_queue.stop_worker()


# ── Pages ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    stats = task_queue.stats()
    recent_tasks = task_queue.list_tasks(limit=10)
    providers = available_providers()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "tasks": recent_tasks,
        "providers": providers,
    })


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, status: str = ""):
    tasks = task_queue.list_tasks(status=status if status else None)
    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "tasks": tasks,
        "current_status": status,
    })


@app.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: int):
    task = task_queue.get_task(task_id)
    if not task:
        return HTMLResponse("<h2>Task not found</h2>", status_code=404)
    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "task": task,
    })


# ── API Endpoints ────────────────────────────────────────

@app.post("/api/tasks")
async def create_task(
    description: str = Form(...),
    repo_url: str = Form(""),
    llm_provider: str = Form("auto"),
    priority: str = Form("normal"),
    files: list[UploadFile] = File(default=[]),
):
    """Create a new task from the web form."""
    attachment_texts = []

    for uploaded_file in files:
        if uploaded_file.filename:
            content = await uploaded_file.read()

            # Save file
            save_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.filename}"
            save_path.write_bytes(content)

            # Extract text from common formats
            text = _extract_text(content, uploaded_file.filename)
            if text:
                attachment_texts.append(f"[File: {uploaded_file.filename}]\n{text}")

    doc_id = task_queue.add_task(
        description=description,
        repo_url=repo_url,
        llm_provider=llm_provider,
        attachment_texts=attachment_texts,
        priority=priority,
    )

    return RedirectResponse(url=f"/tasks/{doc_id}", status_code=303)


@app.get("/api/tasks")
async def api_list_tasks(status: str = ""):
    tasks = task_queue.list_tasks(status=status if status else None)
    return {"tasks": tasks}


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: int):
    task = task_queue.get_task(task_id)
    if not task:
        return {"error": "Task not found"}, 404
    return {"task": task}


@app.get("/api/stats")
async def api_stats():
    return task_queue.stats()


# HTMX partial endpoints
@app.get("/partials/task-rows", response_class=HTMLResponse)
async def task_rows_partial(request: Request):
    tasks = task_queue.list_tasks(limit=10)
    return templates.TemplateResponse("partials/task_rows.html", {
        "request": request,
        "tasks": tasks,
    })


@app.get("/partials/stats", response_class=HTMLResponse)
async def stats_partial(request: Request):
    stats = task_queue.stats()
    return templates.TemplateResponse("partials/stats.html", {
        "request": request,
        "stats": stats,
    })


# ── Helpers ──────────────────────────────────────────────

def _extract_text(content: bytes, filename: str) -> str:
    """Extract readable text from uploaded file."""
    lower = filename.lower()

    if lower.endswith((".txt", ".md", ".markdown", ".rst", ".csv")):
        return content.decode("utf-8", errors="replace")

    if lower.endswith((".py", ".js", ".ts", ".html", ".css", ".yml", ".yaml", ".json", ".sh", ".toml")):
        return content.decode("utf-8", errors="replace")

    if lower.endswith(".pdf"):
        # Basic text extraction — could add pdfplumber later
        try:
            text = content.decode("latin-1", errors="replace")
            # Strip binary noise, keep readable parts
            readable = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
            return readable[:5000] if readable.strip() else "(PDF — could not extract text)"
        except Exception:
            return "(PDF — could not extract text)"

    return f"(Binary file: {filename})"
