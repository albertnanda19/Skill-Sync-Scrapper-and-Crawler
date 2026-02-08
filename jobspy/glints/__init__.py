from __future__ import annotations

import math
import random
import time
from datetime import datetime, timedelta
from typing import Any, Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from jobspy.model import JobPost, JobResponse, Location, Scraper, ScraperInput, Site
from jobspy.util import create_logger, create_session

log = create_logger("Glints")


class Glints(Scraper):
    base_url = "https://glints.com"

    delay = 1.0
    band_delay = 1.5
    jobs_per_page = 20
    max_pages = 100
    max_attempts = 4

    def __init__(
        self,
        proxies: list[str] | str | None = None,
        ca_cert: str | None = None,
        user_agent: str | None = None,
    ):
        super().__init__(Site.GLINTS, proxies=proxies, ca_cert=ca_cert, user_agent=user_agent)
        self.session = create_session(
            proxies=self.proxies,
            ca_cert=ca_cert,
            is_tls=True,
            has_retry=False,
            clear_cookies=True,
        )
        self._base_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9,id;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": self.user_agent
            or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }

        self.scraper_input: ScraperInput | None = None
        self.seen_urls: set[str] = set()

    def scrape(self, scraper_input: ScraperInput) -> JobResponse:
        self.scraper_input = scraper_input

        job_list: list[JobPost] = []
        page = 1

        target = scraper_input.results_wanted + (scraper_input.offset or 0)
        max_pages = min(
            self.max_pages,
            max(1, math.ceil(target / self.jobs_per_page) + 2),
        )

        while len(self.seen_urls) < target and page <= max_pages:
            log.info(f"search page: {page} / {max_pages}")
            try:
                jobs = self._scrape_page(page)
            except Exception as e:
                log.error(f"Glints: failed to scrape page {page}: {e}")
                break

            if not jobs:
                break

            job_list.extend(jobs)
            page += 1

            if len(self.seen_urls) < target:
                time.sleep(random.uniform(self.delay, self.delay + self.band_delay))

        start = scraper_input.offset or 0
        end = start + scraper_input.results_wanted
        return JobResponse(jobs=job_list[start:end])

    def _scrape_page(self, page: int) -> list[JobPost]:
        url = self._build_list_url(page)
        resp = self._get(url)
        if resp is None:
            return []
        status_code = getattr(resp, "status_code", None)
        if status_code not in range(200, 400):
            return []

        soup = BeautifulSoup(getattr(resp, "text", ""), "html.parser")

        jobs = self._parse_jobs_from_next_data(soup)
        if jobs:
            return jobs

        return self._parse_jobs_from_html(soup)

    def _get(self, url: str):
        timeout = int(getattr(self.scraper_input, "request_timeout", 60) or 60)
        backoff = 1.0
        for attempt in range(self.max_attempts):
            try:
                resp = self._session_get(url, timeout=timeout)
                status_code = getattr(resp, "status_code", None)
                if status_code in (403, 429):
                    raise RuntimeError(f"blocked: status={status_code}")
                return resp
            except Exception as e:
                if attempt == self.max_attempts - 1:
                    log.error(f"Glints: request failed: {e}")
                    return None
                sleep_s = backoff + random.uniform(0, 0.5)
                time.sleep(sleep_s)
                backoff = min(backoff * 2.0, 8.0)
        return None

    def _session_get(self, url: str, *, timeout: int):
        try:
            return self.session.get(
                url,
                headers=self._base_headers,
                timeout_seconds=timeout,
            )
        except TypeError:
            return self.session.get(
                url,
                headers=self._base_headers,
                timeout=timeout,
            )

    def _build_list_url(self, page: int) -> str:
        params: list[str] = [f"page={page}"]
        if self.scraper_input and self.scraper_input.search_term:
            params.append(f"keyword={self.scraper_input.search_term}")
        if self.scraper_input and self.scraper_input.location:
            params.append(f"location={self.scraper_input.location}")
        return f"{self.base_url}/id/lowongan-kerja?{'&'.join(params)}"

    def _parse_jobs_from_next_data(self, soup: BeautifulSoup) -> list[JobPost]:
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return []

        try:
            import json

            payload = json.loads(script.string)
        except Exception:
            return []

        page_props = (
            payload.get("props", {})
            .get("pageProps", {})
        )

        initial_jobs = page_props.get("initialJobs")
        jobs_in_page = None
        if isinstance(initial_jobs, dict):
            jobs_in_page = initial_jobs.get("jobsInPage")

        items: list[dict[str, Any]] = []
        if isinstance(jobs_in_page, list):
            for job in jobs_in_page:
                if not isinstance(job, dict):
                    continue
                title = job.get("title")
                job_id = job.get("id")
                if not title or not job_id:
                    continue

                company_name = (job.get("company") or {}).get("name")
                location_str = None
                loc = job.get("location")
                if isinstance(loc, dict):
                    location_str = loc.get("formattedName") or loc.get("name")
                location_str = location_str or job.get("city")

                slug = _slugify(str(title))
                job_url = f"{self.base_url}/id/opportunities/jobs/{slug}/{job_id}"

                items.append(
                    {
                        "title": str(title),
                        "job_url": job_url,
                        "company_name": str(company_name) if company_name else None,
                        "location": str(location_str) if location_str else None,
                        "id": job_id,
                        "posted_at": job.get("createdAt") or job.get("updatedAt"),
                    }
                )

            return self._items_to_job_posts(items)

        for obj in _walk_json(payload):
            if not isinstance(obj, dict):
                continue

            title = obj.get("title") or obj.get("jobTitle")
            url = (
                obj.get("jobUrl")
                or obj.get("url")
                or obj.get("absoluteUrl")
                or obj.get("opportunityUrl")
            )
            if not title or not url:
                continue

            company_name = (
                obj.get("companyName")
                or (obj.get("company") or {}).get("name")
                or obj.get("employerName")
            )
            location_str = obj.get("location") or obj.get("locationName")

            items.append(
                {
                    "title": str(title),
                    "job_url": str(url),
                    "company_name": str(company_name) if company_name else None,
                    "location": str(location_str) if location_str else None,
                    "id": obj.get("id") or obj.get("opportunityId") or obj.get("jobId"),
                    "posted_at": obj.get("postedAt") or obj.get("postedDate") or obj.get("createdAt"),
                }
            )

        return self._items_to_job_posts(items)

    def _parse_jobs_from_html(self, soup: BeautifulSoup) -> list[JobPost]:
        anchors = soup.find_all("a", href=True)
        items: list[dict[str, Any]] = []
        for a in anchors:
            href = a.get("href")
            if not href or "/opportunities/jobs/" not in href:
                continue

            job_url = urljoin(self.base_url, href)
            title = None
            h3 = a.find("h3")
            if h3:
                title = h3.get_text(strip=True)
            if not title:
                title = a.get_text(" ", strip=True)

            if not title:
                continue

            company_name = None
            company_candidate = a.find("a")
            if company_candidate:
                company_name = company_candidate.get_text(strip=True) or None

            items.append(
                {
                    "title": title,
                    "job_url": job_url,
                    "company_name": company_name,
                    "location": None,
                    "id": None,
                    "posted_at": None,
                }
            )

        return self._items_to_job_posts(items)

    def _items_to_job_posts(self, items: list[dict[str, Any]]) -> list[JobPost]:
        jobs: list[JobPost] = []

        for it in items:
            job_url = it.get("job_url")
            if not job_url:
                continue
            if not isinstance(job_url, str):
                continue
            if not job_url.startswith("http"):
                job_url = urljoin(self.base_url, job_url)

            if job_url in self.seen_urls:
                continue
            self.seen_urls.add(job_url)

            title = it.get("title")
            if not title or not isinstance(title, str):
                continue

            company_name = it.get("company_name")
            location_str = it.get("location")
            location = None
            if location_str and isinstance(location_str, str):
                location = Location(city=location_str)

            date_posted = _parse_posted_date(it.get("posted_at"))

            job_id = it.get("id")
            if job_id is None:
                job_id = f"gl-{abs(hash(job_url))}"

            jobs.append(
                JobPost(
                    id=f"gl-{job_id}" if not str(job_id).startswith("gl-") else str(job_id),
                    title=title,
                    company_name=company_name,
                    location=location,
                    date_posted=date_posted,
                    job_url=job_url,
                )
            )

        return jobs


def _walk_json(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_json(v)


def _parse_posted_date(value: Any):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 10_000_000_000:  # ms
                ts /= 1000.0
            return datetime.fromtimestamp(ts).date()

        if isinstance(value, str):
            v = value.strip()
            if not v:
                return None

            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
            except Exception:
                pass

            v_low = v.lower()
            if "day" in v_low and "ago" in v_low:
                import re

                m = re.search(r"(\d+)", v_low)
                if m:
                    days = int(m.group(1))
                    return (datetime.now() - timedelta(days=days)).date()

    except Exception:
        return None

    return None


def _slugify(text: str) -> str:
    import re

    t = text.lower().strip()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    t = re.sub(r"-+", "-", t).strip("-")
    return t or "job"
