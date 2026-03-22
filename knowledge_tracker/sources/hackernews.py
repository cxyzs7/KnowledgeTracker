import logging
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
HN_API = "https://hn.algolia.com/api/v1/search"


def fetch(keywords: list[str], max_results: int = 50) -> list[Article]:
    query = " OR ".join(keywords)
    try:
        resp = httpx.get(
            HN_API,
            params={"query": query, "tags": "story", "hitsPerPage": max_results},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("HackerNews fetch failed: %s", e)
        return []

    articles = []
    for hit in resp.json().get("hits", []):
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
        articles.append(Article(
            url=url,
            title=hit.get("title", ""),
            description=hit.get("story_text") or "",
            source="hackernews",
            author=hit.get("author"),
            score=hit.get("points", 0),
        ))
    return articles
