import logging
from datetime import datetime, timedelta, timezone

import requests

from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "KnowledgeTracker/1.0 (personal knowledge bot)"}


def fetch(subreddits: list[str], limit: int = 25) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles = []

    for sub in subreddits:
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{sub}/hot.json",
                params={"limit": limit},
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            for child in resp.json().get("data", {}).get("children", []):
                post = child.get("data", {})
                created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
                if created < cutoff:
                    continue
                articles.append(Article(
                    url=f"https://reddit.com{post.get('permalink', '')}",
                    title=post.get("title", ""),
                    description=post.get("selftext", "")[:500],
                    source="reddit",
                    author=post.get("author"),
                    score=post.get("score", 0),
                ))
        except Exception as e:
            logger.warning("Reddit fetch failed for r/%s: %s", sub, e)

    return articles
