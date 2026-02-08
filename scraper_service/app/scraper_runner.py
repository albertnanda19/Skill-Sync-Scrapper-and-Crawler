from __future__ import annotations

import asyncio
import logging
import time
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


SITES: list[str] = ["indeed", "linkedin", "glassdoor", "google", "glints"]

scrape_logger = logging.getLogger("app.scrape")


def _chunked(items: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    size = max(1, int(chunk_size))
    return [items[i : i + size] for i in range(0, len(items), size)]


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


async def _get_source_id(site: str) -> uuid.UUID | None:
    async with AsyncSessionLocal() as db:
        source_row = (
            await db.execute(select(JobSource).where(JobSource.name == site))
        ).scalar_one_or_none()
        if source_row is None:
            return None
        return source_row.id


async def _scrape_site_and_store(*, task_id: str, site: str, query: str, location: str) -> int:
    start = time.perf_counter()
    scrape_logger.info(
        "site scrape start | task_id=%s site=%s query=%s location=%s",
        task_id,
        site,
        query,
        location,
    )

    source_id = await _get_source_id(site)
    if source_id is None:
        scrape_logger.warning(
            "site scrape skipped (source not seeded) | task_id=%s site=%s",
            task_id,
            site,
        )
        trigger_scrape_completed_webhook(task_id=task_id, keyword=query, source=site)
        return 0

    df: pd.DataFrame | None = None
    error: str | None = None
    try:
        df = await asyncio.wait_for(
            _scrape_one_site(site=site, query=query, location=location),
            timeout=settings.SCRAPE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        error = f"timeout_after={settings.SCRAPE_TIMEOUT_SECONDS}s"
    except Exception as e:
        error = str(e)

    duration_s = time.perf_counter() - start

    if error is not None:
        scrape_logger.error(
            "site scrape failed | task_id=%s site=%s duration_s=%.2f error=%s",
            task_id,
            site,
            duration_s,
            error,
        )
        trigger_scrape_completed_webhook(task_id=task_id, keyword=query, source=site)
        return 0

    if df is None or len(df) == 0:
        scrape_logger.info(
            "site scrape done (no results) | task_id=%s site=%s duration_s=%.2f",
            task_id,
            site,
            duration_s,
        )
        trigger_scrape_completed_webhook(task_id=task_id, keyword=query, source=site)
        return 0

    records = df.to_dict(orient="records")
    rows: list[dict[str, Any]] = []
    for r in records:
        normalized = _normalize_job_record(r, source_id=source_id, site=site)
        if normalized is not None:
            rows.append(normalized)

    if rows:
        chunk_size = int(getattr(settings, "DB_INSERT_CHUNK_SIZE", 500) or 500)
        chunks = _chunked(rows, chunk_size)
        async with AsyncSessionLocal() as db:
            for idx, chunk in enumerate(chunks, start=1):
                stmt = pg_insert(Job).values(chunk)
                stmt = stmt.on_conflict_do_nothing(index_elements=[Job.source_id, Job.url])
                await db.execute(stmt)
                await db.commit()
                scrape_logger.info(
                    "db insert chunk done | task_id=%s site=%s chunk=%s/%s rows=%s",
                    task_id,
                    site,
                    idx,
                    len(chunks),
                    len(chunk),
                )

    found = int(len(df))
    if duration_s >= float(settings.SLOW_SCRAPE_THRESHOLD_SECONDS):
        scrape_logger.warning(
            "site scrape slow | task_id=%s site=%s duration_s=%.2f found=%s threshold_s=%s",
            task_id,
            site,
            duration_s,
            found,
            settings.SLOW_SCRAPE_THRESHOLD_SECONDS,
        )
    else:
        scrape_logger.info(
            "site scrape done | task_id=%s site=%s duration_s=%.2f found=%s",
            task_id,
            site,
            duration_s,
            found,
        )

    trigger_scrape_completed_webhook(task_id=task_id, keyword=query, source=site)

    return found


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
        sites = list(SITES)
        scrape_logger.info(
            "scrape task start | task_id=%s sites=%s sites_concurrency=%s timeout_s=%s slow_threshold_s=%s",
            task_id,
            ",".join(sites),
            settings.SITES_CONCURRENCY,
            settings.SCRAPE_TIMEOUT_SECONDS,
            settings.SLOW_SCRAPE_THRESHOLD_SECONDS,
        )

        sem = asyncio.Semaphore(max(1, int(settings.SITES_CONCURRENCY)))

        async def _bounded(site: str) -> int:
            async with sem:
                return await _scrape_site_and_store(
                    task_id=task_id,
                    site=site,
                    query=query,
                    location=location,
                )

        results = await asyncio.gather(*(_bounded(site) for site in sites), return_exceptions=True)
        for site, res in zip(sites, results, strict=False):
            if isinstance(res, Exception):
                scrape_logger.error(
                    "site scrape crashed | task_id=%s site=%s error=%s",
                    task_id,
                    site,
                    str(res),
                )
                continue
            total_found += int(res)

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

        scrape_logger.info(
            "scrape task completed | task_id=%s total_found=%s",
            task_id,
            total_found,
        )

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

        scrape_logger.exception(
            "scrape task failed | task_id=%s error=%s",
            task_id,
            str(e),
        )
