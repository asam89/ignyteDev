"""
IgnyteDev Web Dashboard — FastAPI + HTMX.

Submit tasks, upload requirements, view queue, manage connected projects,
preview deployments, and monitor fleet.
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
from bot.core.project_registry import ProjectRegistry
from bot.core.preview_deployer import PreviewDeployer
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
app = FastAPI(title="IgnyteDev Dashboard", version="2.0.0")
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR / "static"), name="static")
templates = Jinja2Templates(directory=DASHBOARD_DIR / "templates")

# Shared state
task_queue = TaskQueue(DATA_DIR)
task_processor = TaskProcessor(REPO_PATH, GH_TOKEN, TARGET_ENV)
task_queue.set_processor(task_processor)
project_registry = ProjectRegistry(DATA_DIR)
preview_deployer = PreviewDeployer()


@app.on_event("startup")
async def startup():
    asyncio.create_task(task_queue.run_worker())
    log.info("Dashboard started, task worker running")


@app.on_event("shutdown")
async def shutdown():
    task_queue.stop_worker()


# ── Dashboard Pages ──────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    stats = task_queue.stats()
    recent_tasks = task_queue.list_tasks(limit=10)
    providers = available_providers()
    projects = project_registry.list_projects()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "tasks": recent_tasks,
        "providers": providers,
        "projects": projects,
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


# ── Projects Pages ───────────────────────────────────────

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    projects = project_registry.list_projects()
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "projects": projects,
    })


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail_page(request: Request, project_id: int):
    project = project_registry.get_project_by_id(project_id)
    if not project:
        return HTMLResponse("<h2>Project not found</h2>", status_code=404)

    # Get preview status
    preview_status = preview_deployer.get_preview_status(project["name"])

    # Get tasks for this project
    all_tasks = task_queue.list_tasks()
    project_tasks = [t for t in all_tasks if t.get("repo_url") == project.get("repo_url")]

    providers = available_providers()

    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "project": project,
        "preview_status": preview_status,
        "tasks": project_tasks,
        "providers": providers,
    })


# ── Task API ─────────────────────────────────────────────

@app.post("/api/tasks")
async def create_task(
    description: str = Form(...),
    repo_url: str = Form(""),
    llm_provider: str = Form("auto"),
    priority: str = Form("normal"),
    project_id: str = Form(""),
    build_preview: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    """Create a new task from the web form."""
    attachment_texts = []

    for uploaded_file in files:
        if uploaded_file.filename:
            content = await uploaded_file.read()

            save_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.filename}"
            save_path.write_bytes(content)

            text = _extract_text(content, uploaded_file.filename)
            if text:
                attachment_texts.append(f"[File: {uploaded_file.filename}]\n{text}")

    # If project_id given, use the project's repo_url
    if project_id:
        project = project_registry.get_project_by_id(int(project_id))
        if project:
            repo_url = project["repo_url"]
            project_registry.increment_task_count(int(project_id))

    doc_id = task_queue.add_task(
        description=description,
        repo_url=repo_url,
        llm_provider=llm_provider,
        attachment_texts=attachment_texts,
        priority=priority,
    )

    # If build_preview checked, mark task for preview build after completion
    if build_preview == "on":
        task_queue.update_task(doc_id, build_preview=True, project_id=int(project_id) if project_id else None)

    if project_id:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
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


# ── Project API ──────────────────────────────────────────

@app.post("/api/projects")
async def create_project(
    name: str = Form(...),
    repo_url: str = Form(...),
    description: str = Form(""),
    public_url: str = Form(""),
    framework: str = Form("auto"),
    docker_port: int = Form(3000),
    auto_deploy: str = Form(""),
):
    """Connect a new project."""
    try:
        project = project_registry.add_project(
            name=name,
            repo_url=repo_url,
            description=description,
            public_url=public_url,
            framework=framework,
            docker_port=docker_port,
            auto_deploy=(auto_deploy == "on"),
        )
        return RedirectResponse(url=f"/projects/{project['id']}", status_code=303)
    except ValueError as e:
        return HTMLResponse(f"<h2>Error: {e}</h2>", status_code=400)


@app.post("/api/projects/{project_id}/deploy-preview")
async def deploy_preview(project_id: int):
    """Build and deploy a preview container for a project."""
    project = project_registry.get_project_by_id(project_id)
    if not project:
        return {"error": "Project not found"}, 404

    repo_path = task_processor._get_repo_path(project["repo_url"])

    result = preview_deployer.deploy_preview(
        project_name=project["name"],
        repo_path=repo_path,
        framework=project.get("framework", "auto"),
        port=project.get("docker_port", 3000),
    )

    project_registry.update_project(
        project_id,
        preview_container=result.get("container_name"),
        preview_url=result.get("preview_url"),
    )

    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@app.post("/api/projects/{project_id}/stop-preview")
async def stop_preview(project_id: int):
    project = project_registry.get_project_by_id(project_id)
    if not project:
        return {"error": "Project not found"}, 404

    preview_deployer.stop_preview(project["name"])
    project_registry.update_project(project_id, preview_container=None, preview_url=None)

    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


@app.get("/api/projects/{project_id}/logs")
async def preview_logs(project_id: int):
    project = project_registry.get_project_by_id(project_id)
    if not project:
        return {"error": "Project not found"}
    logs = preview_deployer.get_preview_logs(project["name"])
    return {"logs": logs}


# ── HTMX Partials ────────────────────────────────────────

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


@app.get("/partials/project-cards", response_class=HTMLResponse)
async def project_cards_partial(request: Request):
    projects = project_registry.list_projects()
    return templates.TemplateResponse("partials/project_cards.html", {
        "request": request,
        "projects": projects,
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
        try:
            text = content.decode("latin-1", errors="replace")
            readable = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
            return readable[:5000] if readable.strip() else "(PDF — could not extract text)"
        except Exception:
            return "(PDF — could not extract text)"

    return f"(Binary file: {filename})"
