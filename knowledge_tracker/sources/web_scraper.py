import logging
import feedparser
import httpx
from bs4 import BeautifulSoup
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def fetch_feeds(feed_urls: list[str]) -> list[Article]:
    articles = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                articles.append(Article(
                    url=entry.get("link", ""),
                    title=entry.get("title", ""),
                    description=entry.get("summary", "")[:500],
                    source="feed",
                    author=entry.get("author"),
                    score=0,
                ))
        except Exception as e:
            logger.warning("Feed fetch failed %s: %s", url, e)
    return articles


def fetch_url(url: str) -> str:
    """Fetch full page text content. Returns empty string on failure."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "KnowledgeTracker/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        logger.warning("fetch_url failed %s: %s", url, e)
        return ""
