"""Pydantic request/response models for the API."""

from typing import Any, Optional
from pydantic import BaseModel


class AuditRequest(BaseModel):
    model: str
    provider: str
    scanners: Optional[list[str]] = None
    config_overrides: Optional[dict[str, Any]] = None


class AuditResponse(BaseModel):
    job_id: str
    status: str
    status_url: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
