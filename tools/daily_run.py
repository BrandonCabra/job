from tools.fetch_jobs import fetch
from main import run as process_jobs


def main() -> None:
    jobs = fetch()
    if not jobs:
        print("No hay ofertas nuevas para procesar.")
        return
    process_jobs(jobs)


if __name__ == "__main__":
    main()
