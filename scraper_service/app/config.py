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


settings = Settings()
