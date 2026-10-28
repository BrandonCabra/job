import os
from pathlib import Path

from tools.scraper import DEFAULT_ROLE_QUERIES, fetch_and_store


def fetch() -> list:
    root = Path(__file__).parents[1]
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env", override=True)
    except ModuleNotFoundError:
        pass
    path = root / "data" / "jobs.json"
    queries = [item.strip() for item in os.getenv("JSEARCH_QUERIES", "").split(",") if item.strip()]
    queries = queries or DEFAULT_ROLE_QUERIES
    feeds = [item.strip() for item in os.getenv("JOB_RSS_FEEDS", "").split(",") if item.strip()]
    limit = min(int(os.getenv("MAX_OLLAMA_JOBS", "50")), 50)
    jobs = fetch_and_store(
        path,
        queries,
        os.getenv("JSEARCH_LOCATION", ""),
        limit,
        feeds,
    )
    print(f"Ofertas nuevas o actualizadas: {len(jobs)}; catálogo total limitado a {limit}.")
    return jobs


def main() -> None:
    fetch()


if __name__ == "__main__":
    main()
