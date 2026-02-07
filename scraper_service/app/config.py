import os

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    MAX_RESULTS_PER_SITE: int = _int_env("MAX_RESULTS_PER_SITE", 50)
    SCRAPE_TIMEOUT_SECONDS: int = _int_env("SCRAPE_TIMEOUT_SECONDS", 120)

    GO_BACKEND_URL: str = os.getenv("GO_BACKEND_URL", "")
    INTERNAL_TOKEN: str = os.getenv("INTERNAL_TOKEN", "")
    WEBHOOK_TIMEOUT_SECONDS: int = _int_env("WEBHOOK_TIMEOUT_SECONDS", 5)
    WEBHOOK_MAX_RETRIES: int = _int_env("WEBHOOK_MAX_RETRIES", 5)


settings = Settings()
