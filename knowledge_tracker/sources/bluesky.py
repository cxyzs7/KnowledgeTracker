import logging, re
import httpx
from atproto import Client
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
URL_RE = re.compile(r'https?://\S+')


def fetch(hashtags: list[str], accounts: list[str],
          handle: str, password: str) -> list[Article]:
    try:
        client = Client()
        client.login(handle, password)
    except Exception as e:
        logger.warning("Bluesky login failed: %s", e)
        return []

    articles = []
    for tag in hashtags:
        try:
            resp = client.app.bsky.feed.search_posts({"q": tag, "limit": 25})
            for item in resp.feed:
                text = item.post.record.text
                urls = URL_RE.findall(text)
                url = urls[0] if urls else f"https://bsky.app/profile/{item.post.author.handle}"
                articles.append(Article(
                    url=url,
                    title=text[:100],
                    description=text,
                    source="bluesky",
                    author=item.post.author.handle,
                    score=0,
                ))
        except Exception as e:
            logger.warning("Bluesky fetch failed for %s: %s", tag, e)

    for account in accounts:
        try:
            resp = client.app.bsky.feed.get_author_feed({"actor": account, "limit": 20})
            for item in resp.feed:
                text = item.post.record.text
                urls = URL_RE.findall(text)
                url = urls[0] if urls else f"https://bsky.app/profile/{account}"
                articles.append(Article(
                    url=url, title=text[:100], description=text,
                    source="bluesky", author=account, score=0,
                ))
        except Exception as e:
            logger.warning("Bluesky account fetch failed %s: %s", account, e)

    return articles
