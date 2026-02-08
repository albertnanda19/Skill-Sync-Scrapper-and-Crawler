from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


ScrapeStatus = Literal["pending", "running", "completed", "failed"]


class ScrapeRequest(BaseModel):
    query: str = Field(min_length=1)
    location: str = Field(min_length=1)


class ScrapeCreateResponse(BaseModel):
    task_id: str
    status: ScrapeStatus


class ScrapeStatusResponse(BaseModel):
    task_id: str
    status: ScrapeStatus
    total_found: int | None = None
    error_message: Optional[str] = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScrapeDeleteResponse(BaseModel):
    task_id: str
    deleted: bool
