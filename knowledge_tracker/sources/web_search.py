import logging, os
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def fetch(query: str, provider: str = "tavily", max_results: int = 10) -> list[Article]:
    if provider == "tavily":
        return _fetch_tavily(query, max_results)
    else:
        logger.error("Unknown web search provider: %s", provider)
        return []


def _fetch_tavily(query: str, max_results: int) -> list[Article]:
    api_key = os.environ.get("TAVILY_API_KEY", "")
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": max_results},
            timeout=15,
        )
        resp.raise_for_status()
        return [
            Article(url=r["url"], title=r.get("title", ""), description=r.get("content", ""),
                    source="web_search", score=0)
            for r in resp.json().get("results", [])
        ]
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return []


