"""Python SDK for the Community AI Audit API.

Usage:
    client = AuditClient("http://localhost:8080", api_key="...")
    job = client.submit_audit("gpt2", "huggingface")
    status = client.get_job(job["job_id"])
"""

import json
from urllib.request import Request, urlopen
from urllib.parse import urljoin


class AuditClient:
    def __init__(self, base_url: str, api_key: str | None = None, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        elif self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body else None
        req = Request(
            urljoin(self.base_url, path), data=data, headers=self._headers(), method=method
        )
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def register(self, email: str, password: str, org_name: str = "default") -> dict:
        return self._request(
            "POST", "/auth/register", {"email": email, "password": password, "org_name": org_name}
        )

    def login(self, email: str, password: str) -> dict:
        return self._request("POST", "/auth/login", {"email": email, "password": password})

    def list_projects(self) -> list:
        return self._request("GET", "/projects")

    def create_project(self, name: str) -> dict:
        return self._request("POST", "/projects", {"name": name})

    def submit_audit(
        self,
        model: str,
        provider: str,
        scanners: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict:
        if project_id:
            return self._request(
                "POST",
                f"/projects/{project_id}/audits",
                {"model": model, "provider": provider, "scanners": scanners},
            )
        return self._request(
            "POST", "/audit", {"model": model, "provider": provider, "scanners": scanners}
        )

    def get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/audit/{job_id}")

    def list_scanners(self) -> list:
        return self._request("GET", "/scanners")
