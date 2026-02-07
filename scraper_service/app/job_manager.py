from __future__ import annotations

import asyncio

from app.scraper_runner import run_scrape_task


async def start_scrape_background(task_id: str, query: str, location: str) -> None:
    asyncio.create_task(run_scrape_task(task_id=task_id, query=query, location=location))
