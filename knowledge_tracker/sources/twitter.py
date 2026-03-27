import logging
import os
from datetime import datetime, timezone, timedelta
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
X_API_BASE = "https://api.twitter.com/2"


def fetch(accounts: list[dict]) -> list[Article]:
    """Fetch recent tweets from curated accounts via X API v2. Returns [] if X_BEARER_TOKEN not set."""
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"Authorization": f"Bearer {token}"}
    articles = []

    for account in accounts:
        try:
            articles.extend(_fetch_account(account, cutoff, headers))
        except Exception as e:
            logger.warning("Twitter fetch failed for @%s: %s", account.get("handle"), e)

    return articles


def _fetch_account(account: dict, cutoff: str, headers: dict) -> list[Article]:
    user_id = account["id"]
    resp = httpx.get(
        f"{X_API_BASE}/users/{user_id}/tweets",
        params={
            "max_results": 5,
            "start_time": cutoff,
            "exclude": "retweets,replies",
            "tweet.fields": "created_at",
        },
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()

    articles = []
    for tweet in resp.json().get("data", []):
        text = tweet["text"]
        tweet_id = tweet["id"]
        handle = account["handle"]
        articles.append(Article(
            url=f"https://twitter.com/{handle}/status/{tweet_id}",
            title=text[:100],
            description=text,
            source="twitter",
            author=account.get("name", handle),
            score=0,
        ))

    return articles
