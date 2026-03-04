import subprocess
import logging

log = logging.getLogger(__name__)

def run_git(cmd: str, cwd: str) -> str:
    """Run a git command and return output."""
    log.info(f"Running git command in {cwd}: {cmd}")
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=120, # Increased timeout
    )
    if result.returncode != 0:
        log.error(f"Git error in {cwd}: {cmd}\nSTDOUT: {result.stdout.strip()}\nSTDERR: {result.stderr.strip()}")
        raise RuntimeError(f"git error: {result.stderr.strip()}")
    log.info(f"Git command success: {cmd}")
    return result.stdout.strip()


def generate_branch_name(task: str) -> str:
    """Create a branch name from the task description."""
    slug = task.lower()[:50] # Increased length slightly
    slug = "".join(c if c.isalnum() or c == ' ' else '' for c in slug)
    slug = slug.strip().replace(' ', '-')
    slug = slug.replace('--', '-') # Clean up double hyphens
    if not slug:
        slug = "untitled-task"
    return f"dev/{slug}" # Prefix with dev/ for clarity
