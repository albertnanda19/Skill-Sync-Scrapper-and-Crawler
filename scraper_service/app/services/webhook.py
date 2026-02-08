from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

import requests

from app.config import settings


logger = logging.getLogger(__name__)


_sent_webhooks_lock = threading.Lock()
_sent_webhooks: set[str] = set()
_in_flight_webhooks: set[str] = set()


def send_scrape_completed_webhook(task_id: str, keyword: str, source: str) -> None:
    if not settings.GO_BACKEND_URL:
        logger.error(
            "Webhook permanently failed | task_id=%s error=GO_BACKEND_URL is not set",
            task_id,
        )
        return

    if not settings.INTERNAL_TOKEN:
        logger.error(
            "Webhook permanently failed | task_id=%s error=INTERNAL_TOKEN is not set",
            task_id,
        )
        return

    dedupe_key = f"{task_id}:{source}"

    with _sent_webhooks_lock:
        if dedupe_key in _sent_webhooks:
            return
        if dedupe_key in _in_flight_webhooks:
            return
        _in_flight_webhooks.add(dedupe_key)

    completed_at = datetime.utcnow().isoformat() + "Z"

    url = settings.GO_BACKEND_URL.rstrip("/") + "/internal/scrape-completed"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": settings.INTERNAL_TOKEN,
    }
    payload: dict[str, Any] = {
        "task_id": task_id,
        "keyword": keyword,
        "source": source,
        "completed_at": completed_at,
    }

    max_retries = max(1, int(settings.WEBHOOK_MAX_RETRIES))
    timeout_seconds = float(settings.WEBHOOK_TIMEOUT_SECONDS)

    last_error: str | None = None

    for attempt in range(1, max_retries + 1):
        retry_num = attempt - 1
        logger.info(
            "Webhook attempt | task_id=%s source=%s retry=%s",
            task_id,
            source,
            retry_num,
        )

        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout_seconds,
            )

            status = resp.status_code

            if 200 <= status < 300:
                logger.info(
                    "Webhook success | task_id=%s source=%s status=%s",
                    task_id,
                    source,
                    status,
                )
                with _sent_webhooks_lock:
                    _sent_webhooks.add(dedupe_key)
                    _in_flight_webhooks.discard(dedupe_key)
                return

            if status in (400, 401, 403):
                last_error = f"non-retriable status={status} body={resp.text[:500]}"
                logger.error(
                    "Webhook permanently failed | task_id=%s source=%s error=%s",
                    task_id,
                    source,
                    last_error,
                )
                with _sent_webhooks_lock:
                    _in_flight_webhooks.discard(dedupe_key)
                return

            if status >= 500:
                last_error = f"retriable status={status} body={resp.text[:500]}"
                logger.error(
                    "Webhook failed | task_id=%s source=%s error=%s",
                    task_id,
                    source,
                    last_error,
                )
            else:
                last_error = f"non-retriable status={status} body={resp.text[:500]}"
                logger.error(
                    "Webhook permanently failed | task_id=%s source=%s error=%s",
                    task_id,
                    source,
                    last_error,
                )
                with _sent_webhooks_lock:
                    _in_flight_webhooks.discard(dedupe_key)
                return

        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.error(
                "Webhook failed | task_id=%s source=%s error=%s",
                task_id,
                source,
                last_error,
            )
        except requests.RequestException as e:
            last_error = f"RequestException: {e}"
            logger.error(
                "Webhook failed | task_id=%s source=%s error=%s",
                task_id,
                source,
                last_error,
            )

        if attempt < max_retries:
            backoff = 2 ** (attempt - 2) if attempt >= 2 else 0
            if backoff > 0:
                time.sleep(backoff)

    logger.error(
        "Webhook permanently failed | task_id=%s source=%s error=%s",
        task_id,
        source,
        last_error or "exhausted retries",
    )

    with _sent_webhooks_lock:
        _in_flight_webhooks.discard(dedupe_key)


def trigger_scrape_completed_webhook(task_id: str, keyword: str, source: str) -> None:
    threading.Thread(
        target=send_scrape_completed_webhook,
        args=(task_id, keyword, source),
        daemon=True,
    ).start()
