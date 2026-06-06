"""
Preview Deployer — builds and runs target projects in Docker containers
so you can preview them at a local URL after code generation.

Supports auto-detection of frameworks (Next.js, Flask, FastAPI, static HTML)
and generates appropriate Dockerfiles if one doesn't exist.
"""

import os
import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "ignyte-previews")
BASE_PORT = int(os.environ.get("PREVIEW_BASE_PORT", "9000"))
HOST_IP = os.environ.get("OCI_HOST", "localhost")


class PreviewDeployer:
    """Builds and runs Docker containers for preview deployments."""

    def __init__(self):
        self._ensure_network()
        self._port_counter = BASE_PORT

    def _ensure_network(self):
        """Create the Docker network if it doesn't exist."""
        try:
            subprocess.run(
                ["docker", "network", "create", DOCKER_NETWORK],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            pass  # Network may already exist

    def deploy_preview(
        self,
        project_name: str,
        repo_path: Path,
        framework: str = "auto",
        port: int = 3000,
        branch: str = "main",
    ) -> dict:
        """
        Build and run a preview container for the project.

        Returns dict with container_name, preview_url, status.
        """
        container_name = f"preview-{project_name}"
        host_port = self._next_port()

        # Stop existing preview if any
        self._stop_container(container_name)

        # Checkout the right branch
        try:
            self._run_cmd(["git", "checkout", branch], cwd=repo_path)
            self._run_cmd(["git", "pull", "origin", branch], cwd=repo_path)
        except Exception as e:
            log.warning(f"Git checkout failed: {e}")

        # Detect framework if auto
        if framework == "auto":
            framework = self._detect_framework(repo_path)
            log.info(f"Auto-detected framework: {framework}")

        # Generate Dockerfile if needed
        dockerfile_path = repo_path / "Dockerfile"
        generated_dockerfile = False
        if not dockerfile_path.exists():
            self._generate_dockerfile(repo_path, framework, port)
            generated_dockerfile = True
            log.info(f"Generated Dockerfile for {framework}")

        # Build
        try:
            self._run_cmd(
                ["docker", "build", "-t", container_name, "."],
                cwd=repo_path,
                timeout=300,
            )
        except Exception as e:
            if generated_dockerfile:
                dockerfile_path.unlink(missing_ok=True)
            return {
                "status": "build_failed",
                "error": str(e),
                "container_name": container_name,
            }

        # Run
        try:
            self._run_cmd([
                "docker", "run", "-d",
                "--name", container_name,
                "--network", DOCKER_NETWORK,
                "-p", f"{host_port}:{port}",
                "--restart", "unless-stopped",
                container_name,
            ])
        except Exception as e:
            return {
                "status": "run_failed",
                "error": str(e),
                "container_name": container_name,
            }

        preview_url = f"http://{HOST_IP}:{host_port}"

        if generated_dockerfile:
            dockerfile_path.unlink(missing_ok=True)

        return {
            "status": "running",
            "container_name": container_name,
            "preview_url": preview_url,
            "host_port": host_port,
            "framework": framework,
        }

    def stop_preview(self, project_name: str) -> bool:
        container_name = f"preview-{project_name}"
        return self._stop_container(container_name)

    def get_preview_status(self, project_name: str) -> dict:
        container_name = f"preview-{project_name}"
        try:
            result = self._run_cmd([
                "docker", "inspect", "--format",
                "{{.State.Status}}:{{.State.StartedAt}}",
                container_name,
            ])
            parts = result.strip().split(":", 1)
            return {
                "container_name": container_name,
                "status": parts[0] if parts else "unknown",
                "started_at": parts[1] if len(parts) > 1 else None,
            }
        except Exception:
            return {"container_name": container_name, "status": "not_found"}

    def get_preview_logs(self, project_name: str, tail: int = 50) -> str:
        container_name = f"preview-{project_name}"
        try:
            return self._run_cmd([
                "docker", "logs", "--tail", str(tail), container_name,
            ])
        except Exception as e:
            return f"Could not fetch logs: {e}"

    def _stop_container(self, container_name: str) -> bool:
        try:
            self._run_cmd(["docker", "stop", container_name], timeout=30)
            self._run_cmd(["docker", "rm", container_name], timeout=15)
            return True
        except Exception:
            return False

    def _next_port(self) -> int:
        port = self._port_counter
        self._port_counter += 1
        return port

    def _detect_framework(self, repo_path: Path) -> str:
        """Detect project framework from files."""
        if (repo_path / "next.config.js").exists() or (repo_path / "next.config.mjs").exists() or (repo_path / "next.config.ts").exists():
            return "nextjs"
        if (repo_path / "package.json").exists():
            try:
                content = (repo_path / "package.json").read_text()
                if '"react"' in content:
                    return "react"
                if '"vue"' in content:
                    return "vue"
                if '"express"' in content:
                    return "express"
            except Exception:
                pass
            return "node"
        if (repo_path / "pyproject.toml").exists() or (repo_path / "requirements.txt").exists():
            try:
                for f in ["pyproject.toml", "requirements.txt"]:
                    fpath = repo_path / f
                    if fpath.exists():
                        content = fpath.read_text()
                        if "fastapi" in content.lower():
                            return "fastapi"
                        if "flask" in content.lower():
                            return "flask"
                        if "django" in content.lower():
                            return "django"
            except Exception:
                pass
            return "python"
        if (repo_path / "index.html").exists():
            return "static"
        return "unknown"

    def _generate_dockerfile(self, repo_path: Path, framework: str, port: int):
        """Generate a Dockerfile for the detected framework."""
        dockerfiles = {
            "nextjs": f"""FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE {port}
CMD ["npm", "start"]
""",
            "react": f"""FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
RUN npm install -g serve
EXPOSE {port}
CMD ["serve", "-s", "build", "-l", "{port}"]
""",
            "node": f"""FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE {port}
CMD ["npm", "start"]
""",
            "express": f"""FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE {port}
CMD ["npm", "start"]
""",
            "fastapi": f"""FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"]
""",
            "flask": f"""FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port={port}"]
""",
            "django": f"""FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["python", "manage.py", "runserver", "0.0.0.0:{port}"]
""",
            "static": f"""FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE {port}
""",
        }
        dockerfile_content = dockerfiles.get(framework, dockerfiles["node"])
        (repo_path / "Dockerfile").write_text(dockerfile_content)

    def _run_cmd(self, cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=cwd,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
        return result.stdout.strip()
