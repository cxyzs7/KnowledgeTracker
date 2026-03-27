import logging
import os
from datetime import datetime, timezone, timedelta
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
SUPADATA_BASE = "https://api.supadata.ai/v1"


def fetch(channels: list[dict]) -> list[Article]:
    """Fetch recent YouTube video transcripts via Supadata. Returns [] if SUPADATA_API_KEY not set."""
    api_key = os.environ.get("SUPADATA_API_KEY")
    if not api_key:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    articles = []

    for channel in channels:
        try:
            articles.extend(_fetch_channel(channel, cutoff, api_key))
        except Exception as e:
            logger.warning("YouTube fetch failed for channel %s: %s", channel.get("name"), e)

    return articles


def _fetch_channel(channel: dict, cutoff: datetime, api_key: str) -> list[Article]:
    headers = {"x-api-key": api_key}
    channel_id = channel["id"]
    channel_name = channel.get("name", channel_id)

    resp = httpx.get(
        f"{SUPADATA_BASE}/youtube/channel/videos",
        params={"id": channel_id, "limit": 10},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()

    articles = []
    for video in resp.json().get("data", []):
        published_str = video.get("publishedAt", "")
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if published < cutoff:
            continue

        try:
            t_resp = httpx.get(
                f"{SUPADATA_BASE}/youtube/transcript",
                params={"videoId": video["id"]},
                headers=headers,
                timeout=30,
            )
            t_resp.raise_for_status()
            description = t_resp.json().get("content", "")[:3000]
        except Exception:
            description = video.get("description", "")[:500]

        articles.append(Article(
            url=f"https://www.youtube.com/watch?v={video['id']}",
            title=video.get("title", ""),
            description=description,
            source="youtube",
            author=channel_name,
            score=0,
        ))

    return articles
