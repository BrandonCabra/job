import os
from pathlib import Path

from tools.scraper import DEFAULT_ROLE_QUERIES, fetch_and_store


def fetch() -> list:
    root = Path(__file__).parents[1]
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip():
                os.environ[key.strip()] = value.strip().strip("\"'")
    path = root / "data" / "jobs.json"
    queries = [item.strip() for item in os.getenv("JSEARCH_QUERIES", "").split(",") if item.strip()]
    queries = queries or DEFAULT_ROLE_QUERIES
    feeds = [item.strip() for item in os.getenv("JOB_RSS_FEEDS", "").split(",") if item.strip()]
    limit = min(int(os.getenv("MAX_OLLAMA_JOBS", "50")), 50)
    if os.getenv("STORAGE_BACKEND", "json").lower() == "sqlite":
        from tools.storage import load_jobs, migrate_json, save_jobs as save_db_jobs

        database = root / os.getenv("JOB_DB_PATH", "data/jobs.db")
        if not database.is_absolute():
            database = root / database
        migrate_json(path, database)
        jobs = fetch_and_store(path, queries, os.getenv("JSEARCH_LOCATION", ""), limit, feeds)
        save_db_jobs(database, jobs, limit)
    else:
        jobs = fetch_and_store(path, queries, os.getenv("JSEARCH_LOCATION", ""), limit, feeds)
    print(f"Ofertas nuevas o actualizadas: {len(jobs)}; catálogo total limitado a {limit}.")
    return jobs


def main() -> None:
    fetch()


if __name__ == "__main__":
    main()
