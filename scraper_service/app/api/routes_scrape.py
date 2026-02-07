from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.job_manager import start_scrape_background
from app.models import ScrapeTask
from app.schemas import ScrapeCreateResponse, ScrapeRequest


router = APIRouter(tags=["scrape"])


@router.post("/scrape", response_model=ScrapeCreateResponse)
async def create_scrape(req: ScrapeRequest, db: AsyncSession = Depends(get_db)) -> ScrapeCreateResponse:
    task = ScrapeTask(id=uuid.uuid4(), query=req.query, location=req.location, status="pending")
    db.add(task)
    await db.commit()

    await start_scrape_background(task_id=str(task.id), query=req.query, location=req.location)

    return ScrapeCreateResponse(task_id=str(task.id), status="pending")
