from pathlib import Path
import logging

log = logging.getLogger(__name__)

def read_repo_context(repo_path: Path, max_files: int = 20) -> str:
    """Read key files from the repo to give Gemini context."""
    context_parts = []
    
    # Always include these if they exist
    priority_files = [
        "README.md", "requirements.txt", "setup.py", "pyproject.toml",
        "Dockerfile", "docker-compose.yml",
    ]

    for fname in priority_files:
        fpath = repo_path / fname
        if fpath.exists():
            try:
                content = fpath.read_text(errors="replace")[:2000]
                context_parts.append(f"--- {fname} ---\n{content}")
            except Exception as e:
                log.warning(f"Could not read priority file {fpath}: {e}")

    # Scan Python files and other relevant code files
    code_files = []
    for ext in ["*.py", "*.js", "*.ts", "*.java", "*.go", "*.sh", "*.yml", "*.yaml", "*.json", "*.html", "*.css"]:
        code_files.extend(sorted(repo_path.rglob(ext)))
    
    # Prioritize code files, limit total files
    scanned_files_count = len(priority_files)
    for fpath in code_files:
        if scanned_files_count >= max_files:
            break
        rel = fpath.relative_to(repo_path)
        if ".git" in str(rel) or "__pycache__" in str(rel) or "node_modules" in str(rel):
            continue
        try:
            content = fpath.read_text(errors="replace")[:3000]
            context_parts.append(f"--- {rel} ---\n{content}")
            scanned_files_count += 1
        except Exception as e:
            log.warning(f"Could not read code file {fpath}: {e}")

    log.info(f"Read context from {len(context_parts)} files.")
    return "\n\n".join(context_parts) if context_parts else "(empty repo)"
