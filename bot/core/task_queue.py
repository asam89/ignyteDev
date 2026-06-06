"""
Task queue — persists tasks in TinyDB, runs them in background.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from tinydb import TinyDB, Query

log = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self, data_dir: Path):
        self.db_path = data_dir / "task_queue.json"
        self.db = TinyDB(self.db_path)
        self._running = False
        self._task_processor = None
        log.info(f"TaskQueue initialized at {self.db_path}")

    def set_processor(self, task_processor):
        self._task_processor = task_processor

    def add_task(
        self,
        description: str,
        repo_url: str = "",
        llm_provider: str = "auto",
        attachment_texts: list[str] | None = None,
        priority: str = "normal",
    ) -> int:
        """Add a task to the queue. Returns the task doc_id."""
        task = {
            "description": description,
            "repo_url": repo_url,
            "llm_provider": llm_provider,
            "attachment_texts": attachment_texts or [],
            "priority": priority,
            "status": "pending",
            "result": None,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
        }
        doc_id = self.db.insert(task)
        log.info(f"Task #{doc_id} queued: {description[:60]}")
        return doc_id

    def get_task(self, doc_id: int) -> dict | None:
        task = self.db.get(doc_id=doc_id)
        if task:
            task["id"] = task.doc_id
        return task

    def list_tasks(self, status: str | None = None, limit: int = 50) -> list[dict]:
        if status:
            Task = Query()
            tasks = self.db.search(Task.status == status)
        else:
            tasks = self.db.all()

        for t in tasks:
            t["id"] = t.doc_id

        tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return tasks[:limit]

    def update_task(self, doc_id: int, **fields):
        self.db.update(fields, doc_ids=[doc_id])

    async def process_next(self):
        """Process the next pending task."""
        if not self._task_processor:
            log.error("No task processor set")
            return

        Task = Query()
        pending = self.db.search(Task.status == "pending")
        if not pending:
            return

        # Sort by priority then created_at
        priority_order = {"high": 0, "normal": 1, "low": 2}
        pending.sort(key=lambda t: (
            priority_order.get(t.get("priority", "normal"), 1),
            t.get("created_at", ""),
        ))

        task = pending[0]
        doc_id = task.doc_id

        self.update_task(
            doc_id,
            status="building",
            started_at=datetime.now().isoformat(),
        )

        try:
            result = await self._task_processor.process_task(
                task_description=task["description"],
                repo_url=task.get("repo_url", ""),
                llm_provider=task.get("llm_provider", "auto"),
                attachment_texts=task.get("attachment_texts"),
            )
            self.update_task(
                doc_id,
                status=result.get("status", "completed"),
                result=result,
                completed_at=datetime.now().isoformat(),
            )
        except Exception as e:
            log.exception(f"Task #{doc_id} failed: {e}")
            self.update_task(
                doc_id,
                status="error",
                result={"status": "error", "message": str(e)},
                completed_at=datetime.now().isoformat(),
            )

    async def run_worker(self):
        """Background worker loop that processes tasks."""
        self._running = True
        log.info("Task queue worker started")
        while self._running:
            try:
                await self.process_next()
            except Exception as e:
                log.exception(f"Worker loop error: {e}")
            await asyncio.sleep(5)

    def stop_worker(self):
        self._running = False

    def stats(self) -> dict:
        Task = Query()
        return {
            "pending": len(self.db.search(Task.status == "pending")),
            "building": len(self.db.search(Task.status == "building")),
            "completed": len(self.db.search(Task.status == "completed")),
            "error": len(self.db.search(Task.status == "error")),
            "total": len(self.db.all()),
        }
