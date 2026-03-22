import logging, os
import praw
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def fetch(subreddits: list[str], limit: int = 25) -> list[Article]:
    try:
        reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID", ""),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
            user_agent="KnowledgeTracker/1.0",
        )
    except Exception as e:
        logger.warning("Reddit init failed: %s", e)
        return []

    articles = []
    for sub in subreddits:
        try:
            for post in reddit.subreddit(sub).hot(limit=limit):
                articles.append(Article(
                    url=post.url,
                    title=post.title,
                    description=post.selftext[:500] if post.selftext else "",
                    source="reddit",
                    author=post.author.name if post.author else None,
                    score=post.score,
                ))
        except Exception as e:
            logger.warning("Reddit fetch failed for r/%s: %s", sub, e)
    return articles
