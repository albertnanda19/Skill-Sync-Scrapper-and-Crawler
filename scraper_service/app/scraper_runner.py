from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

import pandas as pd
from jobspy import scrape_jobs
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Job, JobSource, ScrapeTask
from app.services.webhook import trigger_scrape_completed_webhook


SITES: list[str] = ["indeed", "linkedin", "glassdoor", "google"]


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    if pd.isna(value):
        return None
    return str(value)


def _normalize_job_record(raw: dict[str, Any], *, source_id: uuid.UUID, site: str) -> dict[str, Any] | None:
    job_url = raw.get("job_url") or raw.get("JOB_URL")
    if not job_url or not isinstance(job_url, str):
        return None

    posted_at = raw.get("date_posted") or raw.get("posted_at")
    posted_dt: datetime | None = None
    if posted_at is not None and posted_at != "":
        try:
            ts = pd.to_datetime(posted_at, utc=True, errors="coerce")
            if ts is not pd.NaT and not pd.isna(ts):
                posted_dt = ts.to_pydatetime()
        except Exception:
            posted_dt = None

    now = datetime.utcnow()
    return {
        "id": uuid.uuid4(),
        "source_id": source_id,
        "title": _as_optional_str(raw.get("title") or raw.get("TITLE")),
        "company": _as_optional_str(
            raw.get("company") or raw.get("company_name") or raw.get("COMPANY")
        ),
        "location": _as_optional_str(
            raw.get("location") or raw.get("CITY") or raw.get("LOCATION")
        ),
        "description": _as_optional_str(raw.get("description") or raw.get("DESCRIPTION")),
        "posted_at": posted_dt,
        "scraped_at": now,
        "created_at": now,
        "url": _as_optional_str(job_url),
        "source": site,
        "source_url": _as_optional_str(job_url),
        "is_active": True,
    }


async def _scrape_one_site(site: str, query: str, location: str) -> pd.DataFrame:
    def _run() -> pd.DataFrame:
        return scrape_jobs(
            site_name=[site],
            search_term=query,
            location=location,
            results_wanted=settings.MAX_RESULTS_PER_SITE,
            verbose=0,
            linkedin_fetch_description=True,
        )

    return await asyncio.to_thread(_run)


async def run_scrape_task(task_id: str, query: str, location: str) -> None:
    task_uuid = uuid.UUID(task_id)

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ScrapeTask)
            .where(ScrapeTask.id == task_uuid)
            .values(status="running", updated_at=datetime.utcnow(), error_message=None)
        )
        await db.commit()

    total_found = 0

    try:
        for site in SITES:
            async with AsyncSessionLocal() as db:
                source_row = (
                    await db.execute(select(JobSource).where(JobSource.name == site))
                ).scalar_one_or_none()
                if source_row is None:
                    continue
                source_id = source_row.id

            try:
                df = await asyncio.wait_for(
                    _scrape_one_site(site=site, query=query, location=location),
                    timeout=settings.SCRAPE_TIMEOUT_SECONDS,
                )
            except Exception:
                continue

            if df is None or len(df) == 0:
                continue

            total_found += int(len(df))
            records = df.to_dict(orient="records")

            rows: list[dict[str, Any]] = []
            for r in records:
                normalized = _normalize_job_record(r, source_id=source_id, site=site)
                if normalized is not None:
                    rows.append(normalized)

            if not rows:
                continue

            async with AsyncSessionLocal() as db:
                stmt = pg_insert(Job).values(rows)
                stmt = stmt.on_conflict_do_nothing(index_elements=[Job.source_id, Job.url])
                await db.execute(stmt)
                await db.commit()

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(ScrapeTask)
                .where(ScrapeTask.id == task_uuid)
                .values(
                    status="completed",
                    total_found=total_found,
                    updated_at=datetime.utcnow(),
                )
            )
            await db.commit()

        trigger_scrape_completed_webhook(task_id=task_id, keyword=query, source="all")

    except Exception as e:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(ScrapeTask)
                .where(ScrapeTask.id == task_uuid)
                .values(
                    status="failed",
                    error_message=str(e),
                    updated_at=datetime.utcnow(),
                )
            )
            await db.commit()
