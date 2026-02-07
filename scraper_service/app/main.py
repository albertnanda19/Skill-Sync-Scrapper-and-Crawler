from __future__ import annotations

import uuid

from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes_scrape import router as scrape_router
from app.api.routes_status import router as status_router
from app.database import engine
from app.models import Base


app = FastAPI(title="Scraper Service")

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
