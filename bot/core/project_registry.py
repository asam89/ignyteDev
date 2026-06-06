"""
Connected Projects — persistent project configs with repo URL, deploy target,
Docker preview support, and continuous improvement tracking.
"""

import logging
from pathlib import Path
from datetime import datetime
from tinydb import TinyDB, Query

log = logging.getLogger(__name__)


class ProjectRegistry:
    """Manages connected projects — repos linked for continuous building."""

    def __init__(self, data_dir: Path):
        self.db_path = data_dir / "projects_registry.json"
        self.db = TinyDB(self.db_path)
        log.info(f"ProjectRegistry initialized at {self.db_path}")

    def add_project(
        self,
        name: str,
        repo_url: str,
        description: str = "",
        public_url: str = "",
        framework: str = "auto",
        docker_port: int = 3000,
        auto_deploy: bool = False,
    ) -> dict:
        """Register a new connected project."""
        Project = Query()
        existing = self.db.search(Project.name == name)
        if existing:
            raise ValueError(f"Project '{name}' already exists")

        project = {
            "name": name,
            "repo_url": repo_url,
            "description": description,
            "public_url": public_url,
            "framework": framework,
            "docker_port": docker_port,
            "auto_deploy": auto_deploy,
            "preview_container": None,
            "preview_url": None,
            "last_deployed_commit": None,
            "task_count": 0,
            "status": "connected",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        doc_id = self.db.insert(project)
        project["id"] = doc_id
        log.info(f"Project '{name}' connected: {repo_url}")
        return project

    def get_project(self, name: str) -> dict | None:
        Project = Query()
        results = self.db.search(Project.name == name)
        if results:
            p = results[0]
            p["id"] = p.doc_id
            return p
        return None

    def get_project_by_id(self, doc_id: int) -> dict | None:
        p = self.db.get(doc_id=doc_id)
        if p:
            p["id"] = p.doc_id
        return p

    def list_projects(self) -> list[dict]:
        projects = self.db.all()
        for p in projects:
            p["id"] = p.doc_id
        projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return projects

    def update_project(self, doc_id: int, **fields):
        fields["updated_at"] = datetime.now().isoformat()
        self.db.update(fields, doc_ids=[doc_id])

    def delete_project(self, doc_id: int):
        self.db.remove(doc_ids=[doc_id])

    def increment_task_count(self, doc_id: int):
        project = self.get_project_by_id(doc_id)
        if project:
            self.update_project(doc_id, task_count=project.get("task_count", 0) + 1)
