from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ScrapeTask
from app.schemas import ScrapeStatusResponse


router = APIRouter(tags=["status"])


@router.get("/scrape/{task_id}", response_model=ScrapeStatusResponse)
async def get_status(task_id: str, db: AsyncSession = Depends(get_db)) -> ScrapeStatusResponse:
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid task_id") from e

    result = await db.execute(select(ScrapeTask).where(ScrapeTask.id == task_uuid))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return ScrapeStatusResponse(
        task_id=str(task.id),
        status=task.status,  # type: ignore[arg-type]
        total_found=task.total_found,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
