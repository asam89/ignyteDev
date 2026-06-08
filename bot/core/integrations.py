"""
External Integrations — Jira, Azure DevOps.

Pulls work items from external project management tools and converts them
into IgnyteDev tasks. Supports bidirectional sync (import items, update
status when PRs are opened).
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

import httpx
from tinydb import TinyDB, Query

log = logging.getLogger(__name__)


class IntegrationRegistry:
    """Manages integration credentials and configs."""

    def __init__(self, data_dir: Path):
        self.db_path = data_dir / "integrations.json"
        self.db = TinyDB(self.db_path)
        log.info(f"IntegrationRegistry initialized at {self.db_path}")

    def save_integration(self, provider: str, config: dict) -> int:
        """Save or update an integration config."""
        Integration = Query()
        existing = self.db.search(Integration.provider == provider)
        record = {
            "provider": provider,
            "config": config,
            "status": "connected",
            "updated_at": datetime.now().isoformat(),
        }
        if existing:
            self.db.update(record, Integration.provider == provider)
            return existing[0].doc_id
        else:
            record["created_at"] = datetime.now().isoformat()
            return self.db.insert(record)

    def get_integration(self, provider: str) -> dict | None:
        Integration = Query()
        results = self.db.search(Integration.provider == provider)
        if results:
            r = results[0]
            r["id"] = r.doc_id
            return r
        return None

    def list_integrations(self) -> list[dict]:
        items = self.db.all()
        for item in items:
            item["id"] = item.doc_id
        return items

    def delete_integration(self, provider: str):
        Integration = Query()
        self.db.remove(Integration.provider == provider)


class JiraClient:
    """Jira Cloud REST API client."""

    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (email, api_token)

    def get_issues(
        self,
        project_key: str,
        status: str = "",
        max_results: int = 50,
    ) -> list[dict]:
        """Fetch issues from a Jira project."""
        jql = f"project = {project_key}"
        if status:
            jql += f" AND status = '{status}'"
        jql += " ORDER BY priority DESC, created ASC"

        try:
            resp = httpx.get(
                f"{self.base_url}/rest/api/3/search",
                params={"jql": jql, "maxResults": max_results},
                auth=self.auth,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return [self._normalize_issue(i) for i in data.get("issues", [])]
        except Exception as e:
            log.error(f"Jira fetch failed: {e}")
            return []

    def get_issue(self, issue_key: str) -> dict | None:
        try:
            resp = httpx.get(
                f"{self.base_url}/rest/api/3/issue/{issue_key}",
                auth=self.auth,
                timeout=30,
            )
            resp.raise_for_status()
            return self._normalize_issue(resp.json())
        except Exception as e:
            log.error(f"Jira issue fetch failed: {e}")
            return None

    def add_comment(self, issue_key: str, comment: str):
        """Add a comment to a Jira issue (e.g., PR link)."""
        try:
            resp = httpx.post(
                f"{self.base_url}/rest/api/3/issue/{issue_key}/comment",
                json={
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": comment}],
                        }],
                    }
                },
                auth=self.auth,
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            log.error(f"Jira comment failed: {e}")

    def _normalize_issue(self, issue: dict) -> dict:
        fields = issue.get("fields", {})
        desc_content = fields.get("description", {})
        description = ""
        if isinstance(desc_content, dict):
            # ADF format — extract text
            description = self._extract_adf_text(desc_content)
        elif isinstance(desc_content, str):
            description = desc_content

        return {
            "key": issue.get("key", ""),
            "summary": fields.get("summary", ""),
            "description": description,
            "status": fields.get("status", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", "Medium"),
            "issue_type": fields.get("issuetype", {}).get("name", ""),
            "assignee": (fields.get("assignee") or {}).get("displayName", ""),
            "labels": fields.get("labels", []),
            "url": f"{self.base_url}/browse/{issue.get('key', '')}",
        }

    def _extract_adf_text(self, adf: dict) -> str:
        """Extract plain text from Atlassian Document Format."""
        texts = []
        for block in adf.get("content", []):
            for inline in block.get("content", []):
                if inline.get("type") == "text":
                    texts.append(inline.get("text", ""))
        return "\n".join(texts)


class AzureDevOpsClient:
    """Azure DevOps REST API client."""

    def __init__(self, org_url: str, project: str, pat: str):
        self.org_url = org_url.rstrip("/")
        self.project = project
        self.headers = {
            "Authorization": f"Basic {self._encode_pat(pat)}",
            "Content-Type": "application/json",
        }

    def _encode_pat(self, pat: str) -> str:
        import base64
        return base64.b64encode(f":{pat}".encode()).decode()

    def get_work_items(
        self,
        query: str = "",
        max_results: int = 50,
    ) -> list[dict]:
        """Fetch work items via WIQL query."""
        wiql = query or (
            f"SELECT [System.Id], [System.Title], [System.State] "
            f"FROM WorkItems "
            f"WHERE [System.TeamProject] = '{self.project}' "
            f"AND [System.State] <> 'Closed' "
            f"ORDER BY [Microsoft.VSTS.Common.Priority] ASC"
        )

        try:
            resp = httpx.post(
                f"{self.org_url}/{self.project}/_apis/wit/wiql?api-version=7.0",
                json={"query": wiql},
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            work_item_ids = [wi["id"] for wi in data.get("workItems", [])[:max_results]]
            if not work_item_ids:
                return []

            return self._get_work_items_by_ids(work_item_ids)
        except Exception as e:
            log.error(f"Azure DevOps fetch failed: {e}")
            return []

    def _get_work_items_by_ids(self, ids: list[int]) -> list[dict]:
        """Fetch full work item details by IDs."""
        try:
            id_str = ",".join(str(i) for i in ids)
            resp = httpx.get(
                f"{self.org_url}/{self.project}/_apis/wit/workitems?ids={id_str}&api-version=7.0",
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            return [self._normalize_item(wi) for wi in resp.json().get("value", [])]
        except Exception as e:
            log.error(f"Azure DevOps batch fetch failed: {e}")
            return []

    def add_comment(self, work_item_id: int, comment: str):
        """Add a comment to a work item."""
        try:
            resp = httpx.post(
                f"{self.org_url}/{self.project}/_apis/wit/workitems/{work_item_id}/comments?api-version=7.0-preview.3",
                json={"text": comment},
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            log.error(f"Azure DevOps comment failed: {e}")

    def _normalize_item(self, item: dict) -> dict:
        fields = item.get("fields", {})
        return {
            "id": item.get("id", 0),
            "title": fields.get("System.Title", ""),
            "description": fields.get("System.Description", "") or "",
            "state": fields.get("System.State", ""),
            "priority": str(fields.get("Microsoft.VSTS.Common.Priority", 2)),
            "work_item_type": fields.get("System.WorkItemType", ""),
            "assigned_to": (fields.get("System.AssignedTo") or {}).get("displayName", ""),
            "tags": fields.get("System.Tags", ""),
            "url": item.get("url", ""),
        }


def import_jira_issues(
    integration_config: dict,
    project_key: str,
) -> list[dict]:
    """Import Jira issues as task dicts ready for the queue."""
    client = JiraClient(
        base_url=integration_config["base_url"],
        email=integration_config["email"],
        api_token=integration_config["api_token"],
    )
    issues = client.get_issues(project_key)

    priority_map = {"Highest": "high", "High": "high", "Medium": "normal", "Low": "low", "Lowest": "low"}

    return [{
        "title": f"[{i['key']}] {i['summary']}",
        "description": f"{i['summary']}\n\n{i['description']}" if i["description"] else i["summary"],
        "priority": priority_map.get(i["priority"], "normal"),
        "source": "jira",
        "source_key": i["key"],
        "source_url": i["url"],
    } for i in issues]


def import_ado_items(
    integration_config: dict,
) -> list[dict]:
    """Import Azure DevOps work items as task dicts."""
    client = AzureDevOpsClient(
        org_url=integration_config["org_url"],
        project=integration_config["project"],
        pat=integration_config["pat"],
    )
    items = client.get_work_items()

    priority_map = {"1": "high", "2": "high", "3": "normal", "4": "low"}

    return [{
        "title": f"[ADO-{i['id']}] {i['title']}",
        "description": i["description"] or i["title"],
        "priority": priority_map.get(i["priority"], "normal"),
        "source": "azure_devops",
        "source_key": str(i["id"]),
        "source_url": i["url"],
    } for i in items]
