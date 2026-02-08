from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import ScrapeTask
from app.schemas import ScrapeDeleteResponse


router = APIRouter(prefix="/internal", tags=["internal"])


def _require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    if not settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=500, detail="INTERNAL_TOKEN is not configured")
    if not x_internal_token or x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.delete("/scrape/{task_id}", response_model=ScrapeDeleteResponse)
async def delete_scrape_task(
    task_id: str,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_internal_token),
) -> ScrapeDeleteResponse:
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid task_id") from e

    result = await db.execute(select(ScrapeTask).where(ScrapeTask.id == task_uuid))
    task = result.scalar_one_or_none()
    if task is None:
        return ScrapeDeleteResponse(task_id=task_id, deleted=False)

    if not force and task.status == "running":
        raise HTTPException(status_code=409, detail="Task is running")

    await db.execute(delete(ScrapeTask).where(ScrapeTask.id == task_uuid))
    await db.commit()

    return ScrapeDeleteResponse(task_id=task_id, deleted=True)
