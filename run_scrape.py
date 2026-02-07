import csv
from jobspy import scrape_jobs

keyword = "marketing"
location = "Jakarta"

try:
    jobs = scrape_jobs(
        site_name=["indeed", "linkedin", "zip_recruiter"],
        search_term=keyword,
        google_search_term=f"{keyword} jobs near {location} since yesterday",
        location=location,
        results_wanted=20,
        hours_old=72,
        country_indeed="Indonesia",
        verbose=2,
        linkedin_fetch_description=True,
        # proxies=["user:pass@host:port", "localhost"],
    )

    print(f"Found {len(jobs)} jobs")
    print(jobs.head())
    jobs.to_csv(
        "jobs.csv", quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False
    )
except Exception as e:
    raise SystemExit(f"Scrape failed: {e}")