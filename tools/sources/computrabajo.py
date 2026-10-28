import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from tools.models import Job


def _slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")


def _text(node: object) -> str:
    return node.get_text(" ", strip=True) if node else ""


def parse_computrabajo_html(html: str, base_url: str, limit: int = 10) -> list[Job]:
    """Parse public listing cards without logging in or interacting with anti-bot controls."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[Job] = []
    selectors = ("article", "[data-id]", ".box_offer", ".result-item", ".job-card")
    cards = []
    for selector in selectors:
        cards.extend(soup.select(selector))
    seen: set[str] = set()
    for card in cards:
        link = card.select_one("a[href]")
        if not link:
            continue
        url = link.get("href", "").strip()
        if url.startswith("/"):
            url = "https://co.computrabajo.com" + url
        if url in seen:
            continue
        seen.add(url)
        title = _text(card.select_one("h2, h3, .title, .js-o-link"))
        if not title:
            title = _text(link)
        if not title:
            continue
        company = _text(card.select_one(".company, .empr, [class*='company']"))
        location = _text(card.select_one(".location, .loc, [class*='location']"))
        description = _text(card.select_one(".description, .desc, [class*='description']"))
        jobs.append(Job(
            title=title,
            company=company or "Empresa desconocida",
            description=description,
            url=url or base_url,
            location=location,
            source="computrabajo",
        ))
        if len(jobs) >= limit:
            break
    return jobs


def search_computrabajo(
    queries: list[str],
    location: str,
    limit: int = 10,
    search_url_template: str = "",
    timeout: int = 30,
) -> list[Job]:
    """Fetch a configured public search URL; never attempts authentication or bypasses blocks."""
    if not search_url_template:
        print("Computrabajo omitido: define COMPUTRABAJO_SEARCH_URL_TEMPLATE para habilitarlo.")
        return []
    jobs: list[Job] = []
    per_query = max(1, (limit + len(queries) - 1) // len(queries))
    for query in queries:
        url = search_url_template.format(
            query=quote_plus(query),
            query_slug=_slug(query),
            location=quote_plus(location),
        )
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "job-agent/1.0 (+public-job-search)"},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"no se pudo consultar {url}: {exc}") from exc
        if not response.ok:
            raise RuntimeError(f"Computrabajo respondió HTTP {response.status_code} para {url}")
        jobs.extend(parse_computrabajo_html(response.text, url, per_query))
        if len(jobs) >= limit:
            break
    return jobs[:limit]
