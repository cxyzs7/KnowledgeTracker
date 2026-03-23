import logging
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "KnowledgeTracker/1.0"}


def fetch(subreddits: list[str], limit: int = 25) -> list[Article]:
    articles = []
    for sub in subreddits:
        try:
            resp = httpx.get(
                f"https://www.reddit.com/r/{sub}/hot.json",
                params={"limit": limit},
                headers=HEADERS,
                timeout=15,
                follow_redirects=True,
            )
            resp.raise_for_status()
            for child in resp.json().get("data", {}).get("children", []):
                post = child.get("data", {})
                articles.append(Article(
                    url=post.get("url", ""),
                    title=post.get("title", ""),
                    description=post.get("selftext", "")[:500],
                    source="reddit",
                    author=post.get("author"),
                    score=post.get("score", 0),
                ))
        except Exception as e:
            logger.warning("Reddit fetch failed for r/%s: %s", sub, e)
    return articles
