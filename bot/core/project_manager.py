import logging
from pathlib import Path
from datetime import datetime
from tinydb import TinyDB, Query

log = logging.getLogger(__name__)

class ProjectManager:
    """Manages projects within the bot, likely storing data in a local database."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = self.data_dir / "projects.json"
        self.db = TinyDB(self.db_path)
        log.info(f"ProjectManager initialized, data stored at {self.db_path}")

    def create_project(self, name: str, description: str = "", status: str = "open") -> dict:
        """Create a new project entry."""
        project = {"name": name, "description": description, "status": status, "created_at": str(datetime.now())}
        self.db.insert(project)
        log.info(f"Created project: {name}")
        return project

    def get_project(self, name: str) -> dict | None:
        """Retrieve a project by name."""
        Project = Query()
        result = self.db.search(Project.name == name)
        return result[0] if result else None

    def list_projects(self) -> list[dict]:
        """List all projects."""
        return self.db.all()

    # More methods (update, delete, add tasks, link Obsidian notes, etc.) will go here
