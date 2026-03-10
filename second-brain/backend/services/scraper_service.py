"""
Scraper Service — Fetch URL → extract article content.

Uses httpx for async HTTP + trafilatura for content extraction.
trafilatura is CPU-bound, so runs in asyncio.to_thread().
"""

import asyncio
import logging

from backend.models.schemas import ScrapedArticle

logger = logging.getLogger(__name__)

# Timeout for HTTP requests (seconds)
FETCH_TIMEOUT = 15


async def scrape_url(url: str) -> ScrapedArticle | None:
    """Fetch URL → extract article → return structured content.

    Returns None on failure (timeout, paywall, JS-only, 404).
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — scraping disabled")
        return None

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": "SecondBrain/1.0 (knowledge collector)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None

    # trafilatura is sync + CPU-bound → run in thread
    try:
        result = await asyncio.to_thread(_extract_article, html, url)
        return result
    except Exception as e:
        logger.warning("Failed to extract article from %s: %s", url, e)
        return None


def _extract_article(html: str, url: str) -> ScrapedArticle | None:
    """Sync extraction using trafilatura. Called via to_thread()."""
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed — article extraction disabled")
        return None

    result = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        output_format="txt",
        url=url,
    )

    if not result:
        return None

    # Extract title/author/date from metadata
    title = ""
    author = None
    date = None
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta:
            title = meta.title or ""
            author = meta.author
            date = meta.date
    except Exception:
        pass

    words = len(result.split())
    reading_time = max(1, words // 200)

    return ScrapedArticle(
        title=title,
        content=result,
        author=author,
        date=date,
        word_count=words,
        reading_time=reading_time,
    )
