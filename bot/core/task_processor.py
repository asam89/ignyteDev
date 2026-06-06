"""
Task Processor — generates code from task descriptions and opens PRs.

Supports multiple repos and dual LLM providers (Claude + Gemini).
"""

import os
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

from bot.core.llm import call_llm
from bot.core.git_utils import run_git, generate_branch_name
from bot.core.repo_reader import read_repo_context

log = logging.getLogger(__name__)

REPOS_DIR = Path(os.environ.get("REPOS_DIR", "/repos"))
GH_TOKEN = os.environ.get("GH_TOKEN", "")


class TaskProcessor:
    def __init__(self, repo_path: str, gh_token: str, target_environment: str):
        self.default_repo_path = Path(repo_path)
        self.gh_token = gh_token or GH_TOKEN
        self.target_environment = target_environment
        log.info(f"TaskProcessor initialized, default repo: {self.default_repo_path}")

    def _get_repo_path(self, repo_url: str = "") -> Path:
        """Resolve repo path — clone if needed for multi-repo support."""
        if not repo_url:
            return self.default_repo_path

        # Extract owner/name from URL
        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        repo_owner = repo_url.rstrip("/").split("/")[-2]
        local_path = REPOS_DIR / f"{repo_owner}_{repo_name}"

        if not local_path.exists():
            log.info(f"Cloning {repo_url} to {local_path}")
            REPOS_DIR.mkdir(parents=True, exist_ok=True)
            clone_url = repo_url
            if self.gh_token and "github.com" in repo_url:
                clone_url = repo_url.replace(
                    "https://github.com",
                    f"https://x-access-token:{self.gh_token}@github.com",
                )
            subprocess.run(
                ["git", "clone", clone_url, str(local_path)],
                capture_output=True, text=True, timeout=120,
                check=True,
            )
            # Configure git identity in cloned repo
            run_git('config user.email "bot@ignyteconsulting.com"', local_path)
            run_git('config user.name "IgnyteDev Bot"', local_path)

        return local_path

    async def process_task(
        self,
        task_description: str,
        chat_id: int = 0,
        repo_url: str = "",
        llm_provider: str = "auto",
        attachment_texts: list[str] | None = None,
    ) -> dict:
        """
        Process a task: generate code, commit, push, and open a PR.

        Returns a dict with status info for the dashboard.
        """
        log.info(f"Processing task: {task_description[:80]}...")
        repo_path = self._get_repo_path(repo_url)

        # 1. Generate branch name
        branch_name = generate_branch_name(task_description)

        # 2. Sync and create branch
        try:
            run_git("checkout main", repo_path)
            run_git("pull origin main", repo_path)
            run_git(f"checkout -b {branch_name}", repo_path)
        except RuntimeError as e:
            return {"status": "error", "message": f"Git setup failed: {e}"}

        # 3. Read repo context
        repo_context = read_repo_context(repo_path)

        # 4. Build prompt with optional attachment context
        extra_context = ""
        if attachment_texts:
            extra_context = "\n\n--- Uploaded Requirements ---\n"
            extra_context += "\n\n".join(attachment_texts)

        prompt = self._build_prompt(task_description, repo_context, extra_context)

        # 5. Generate changes with LLM
        try:
            raw_response = call_llm(
                prompt=prompt,
                system=self._system_prompt(),
                provider=llm_provider,
                max_tokens=4096,
            )
            json_response = raw_response.strip().lstrip("```json").lstrip("```").rstrip("```")
            changes = json.loads(json_response)
        except json.JSONDecodeError as e:
            log.error(f"LLM returned invalid JSON: {e}\nResponse: {raw_response[:500]}")
            self._cleanup_branch(repo_path, branch_name)
            return {"status": "error", "message": f"LLM returned invalid JSON: {e}"}
        except Exception as e:
            log.error(f"LLM call failed: {e}")
            self._cleanup_branch(repo_path, branch_name)
            return {"status": "error", "message": f"LLM generation failed: {e}"}

        # 6. Apply changes
        for file_change in changes.get("files", []):
            try:
                self._apply_file_change(file_change, repo_path)
            except Exception as e:
                log.error(f"Failed to apply change: {e}")
                self._cleanup_branch(repo_path, branch_name)
                return {"status": "error", "message": f"Failed to apply changes: {e}"}

        # 7. Commit
        commit_message = changes.get("commit_message", f"feat: {task_description[:50]}")
        try:
            run_git("add .", repo_path)
            run_git(f'commit -m "{commit_message}"', repo_path)
        except RuntimeError as e:
            if "nothing to commit" in str(e):
                self._cleanup_branch(repo_path, branch_name)
                return {"status": "skipped", "message": "No changes generated"}
            self._cleanup_branch(repo_path, branch_name)
            return {"status": "error", "message": f"Commit failed: {e}"}

        # 8. Push
        try:
            run_git(f"push -u origin {branch_name}", repo_path)
        except RuntimeError as e:
            self._cleanup_branch(repo_path, branch_name)
            return {"status": "error", "message": f"Push failed: {e}"}

        # 9. Open PR
        pr_description = changes.get("pr_description", f"Automated PR for: {task_description}")
        pr_url = ""
        try:
            pr_output = run_git(
                f'gh pr create --title "{commit_message}" '
                f'--body "{pr_description}" '
                f'--base main --head {branch_name}',
                repo_path,
            )
            pr_url = pr_output.strip().split("\n")[-1]
        except RuntimeError as e:
            log.warning(f"PR creation failed (branch pushed): {e}")
            pr_url = f"Branch pushed: {branch_name}"
        finally:
            run_git("checkout main", repo_path)

        return {
            "status": "completed",
            "message": f"PR opened: {pr_url}",
            "pr_url": pr_url,
            "branch": branch_name,
            "commit_message": commit_message,
            "files_changed": len(changes.get("files", [])),
        }

    def _cleanup_branch(self, repo_path: Path, branch_name: str):
        """Discard changes and remove branch."""
        try:
            run_git("reset --hard HEAD", repo_path)
            run_git("checkout main", repo_path)
            run_git(f"branch -D {branch_name}", repo_path)
        except RuntimeError:
            pass

    def _system_prompt(self) -> str:
        return (
            "You are an autonomous developer bot. Implement the requested feature or fix. "
            "Respond ONLY with valid JSON."
        )

    def _build_prompt(self, task: str, repo_context: str, extra_context: str = "") -> str:
        return f"""Analyze the codebase and produce exact file changes to accomplish the task.
Respond ONLY with a valid JSON object containing:
- "files": Array of objects with "path", "action" ("create"/"modify"/"delete"), "content" (full file content for create/modify, empty string for delete).
- "commit_message": Concise commit message (e.g., "feat: Add user endpoint").
- "pr_description": Detailed PR description.

If a file is modified, provide its ENTIRE new content.
Ensure code is correct, follows existing conventions, and integrates with the codebase.
Add new dependencies to requirements.txt or package.json if needed.

--- Task ---
{task}
{extra_context}

--- Codebase Context ---
{repo_context}"""

    def _apply_file_change(self, file_change: dict, repo_path: Path):
        """Apply a single file change."""
        file_path = repo_path / file_change["path"]
        action = file_change["action"]
        content = file_change.get("content", "")

        file_path.parent.mkdir(parents=True, exist_ok=True)

        if action in ("create", "modify"):
            file_path.write_text(content)
        elif action == "delete":
            if file_path.exists():
                file_path.unlink()
        else:
            raise ValueError(f"Unknown action: {action}")
