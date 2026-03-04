import logging
from pathlib import Path

log = logging.getLogger(__name__)

class ObsidianManager:
    """Handles integration with an Obsidian vault for Markdown notes."""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        if not self.vault_path.is_dir():
            log.warning(f"Obsidian vault path '{vault_path}' does not exist or is not a directory. Obsidian integration will be limited.")
        log.info(f"ObsidianManager initialized with vault path: {self.vault_path}")

    def read_note(self, note_name: str) -> str | None:
        """Read the content of an Obsidian note."""
        note_path = self.vault_path / f"{note_name}.md"
        if note_path.exists():
            try:
                content = note_path.read_text(encoding="utf-8")
                log.info(f"Read Obsidian note: {note_name}")
                return content
            except Exception as e:
                log.error(f"Failed to read Obsidian note {note_name}: {e}")
                return None
        log.warning(f"Obsidian note '{note_name}.md' not found at {note_path}")
        return None

    def create_note(self, note_name: str, content: str = "", folder: str = "") -> Path:
        """Create a new Obsidian note."""
        target_folder = self.vault_path / folder
        target_folder.mkdir(parents=True, exist_ok=True)
        note_path = target_folder / f"{note_name}.md"
        try:
            note_path.write_text(content, encoding="utf-8")
            log.info(f"Created Obsidian note: {note_path}")
            return note_path
        except Exception as e:
            log.error(f"Failed to create Obsidian note {note_name}: {e}")
            raise

    # More methods (list notes, update notes, parse tasks from notes, etc.) will go here
