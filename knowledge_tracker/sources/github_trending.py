import logging
import httpx
from bs4 import BeautifulSoup
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def fetch(language: str = "") -> list[Article]:
    url = "https://github.com/trending"
    if language:
        url += f"/{language}"
    try:
        resp = httpx.get(url, timeout=15, headers={"User-Agent": "KnowledgeTracker/1.0"})
        resp.raise_for_status()
    except Exception as e:
        logger.warning("GitHub Trending fetch failed: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    for row in soup.select("article.Box-row"):
        link = row.select_one("h2 a")
        if not link:
            continue
        path = link["href"].strip("/")
        repo_url = f"https://github.com/{path}"
        title = path.replace("/", " / ")
        desc_tag = row.select_one("p")
        desc = desc_tag.get_text(strip=True) if desc_tag else ""
        stars_tag = row.select_one(".d-inline-block.float-sm-right")
        stars_text = stars_tag.get_text(strip=True) if stars_tag else ""
        articles.append(Article(
            url=repo_url,
            title=title,
            description=f"{desc} · {stars_text}".strip(" ·"),
            source="github_trending",
            score=0,
        ))
    return articles
