from __future__ import annotations

import logging
import os
import time
import uuid

from fastapi import FastAPI
from fastapi import Request
from sqlalchemy import text

from app.api.routes_scrape import router as scrape_router
from app.api.routes_status import router as status_router
from app.database import engine
from app.models import Base


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
http_logger = logging.getLogger("app.http")


app = FastAPI(title="Scraper Service")


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    start = time.perf_counter()

    client_host = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    query = request.url.query
    user_agent = request.headers.get("user-agent", "")

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000.0
        http_logger.exception(
            "HTTP request failed | client=%s method=%s path=%s query=%s status=%s duration_ms=%.2f user_agent=%s",
            client_host,
            method,
            path,
            query,
            500,
            duration_ms,
            user_agent,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000.0
    http_logger.info(
        "HTTP request | client=%s method=%s path=%s query=%s status=%s duration_ms=%.2f user_agent=%s",
        client_host,
        method,
        path,
        query,
        response.status_code,
        duration_ms,
        user_agent,
    )
    return response

app.include_router(scrape_router)
app.include_router(status_router)


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        seed_sources = [
            (str(uuid.uuid4()), "indeed", "https://www.indeed.com"),
            (str(uuid.uuid4()), "linkedin", "https://www.linkedin.com"),
            (str(uuid.uuid4()), "glassdoor", "https://www.glassdoor.com"),
            (str(uuid.uuid4()), "google", "https://www.google.com"),
        ]

        await conn.execute(
            text(
                """
                INSERT INTO job_sources (id, name, base_url)
                VALUES (:id, :name, :base_url)
                ON CONFLICT (name) DO NOTHING;
                """
            ),
            [{"id": sid, "name": name, "base_url": base_url} for (sid, name, base_url) in seed_sources],
        )
