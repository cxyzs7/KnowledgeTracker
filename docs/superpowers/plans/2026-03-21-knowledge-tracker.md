# KnowledgeTracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python pipeline that generates daily topic digests and weekly deep dives, saved as markdown to an Obsidian vault on GitHub, with semantic dedup, scoring, and preference learning.

**Architecture:** A Python package with clearly separated modules for sources, deduplication, scoring, generation, and vault I/O. The `run.py` CLI dispatches `daily` or `weekly` commands; GitHub Actions provides scheduling. `sentence-transformers` handles local embeddings; Claude API handles digest and deep dive generation.

**Tech Stack:** Python 3.12, anthropic, sentence-transformers (all-MiniLM-L6-v2), scikit-learn, praw, atproto, tavily-python, feedparser, httpx, beautifulsoup4, pyyaml, gitpython, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-knowledge-tracker-design.md`

---

## File Map

```
KnowledgeTracker/
├── config/
│   └── topics.yaml                  # topic + vault config (created in Task 1)
├── knowledge_tracker/               # main package
│   ├── __init__.py
│   ├── models.py                    # Article dataclass, shared types
│   ├── config.py                    # load + validate topics.yaml
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py                  # SourceResult namedtuple, fetch() protocol
│   │   ├── hackernews.py
│   │   ├── reddit.py
│   │   ├── web_scraper.py           # RSS feeds + HTML scraping + Twitter URLs
│   │   ├── web_search.py            # Tavily / Exa
│   │   ├── github_trending.py
│   │   └── bluesky.py
│   ├── dedup.py                     # URL dedup + semantic dedup
│   ├── preferences/
│   │   ├── __init__.py
│   │   ├── store.py                 # read/write preferences.md
│   │   └── scorer.py                # semantic + structural scoring
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── digest.py                # daily digest via Claude
│   │   └── deepdive.py              # weekly deep dive via Claude
│   ├── obsidian/
│   │   ├── __init__.py
│   │   ├── writer.py                # write markdown to vault
│   │   ├── reader.py                # parse digest files for flags + manual links
│   │   └── git_sync.py              # git pull/add/commit/push (local runs only)
│   └── claude_client.py             # Claude API wrapper with retry logic
├── run.py                           # CLI entry point
├── requirements.in                  # unpinned deps
├── requirements.txt                 # pinned (pip-compile output)
├── .github/workflows/
│   ├── daily_digest.yml
│   └── weekly_deepdive.yml
└── tests/
    ├── test_models.py
    ├── test_config.py
    ├── test_dedup.py
    ├── test_scorer.py
    ├── test_reader.py
    ├── test_writer.py
    ├── test_store.py
    ├── test_sources/
    │   ├── test_hackernews.py
    │   ├── test_reddit.py
    │   ├── test_web_scraper.py
    │   ├── test_web_search.py
    │   ├── test_github_trending.py
    │   └── test_bluesky.py
    └── fixtures/
        ├── sample_digest.md
        └── sample_preferences.md
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `knowledge_tracker/__init__.py`
- Create: `requirements.in`
- Create: `config/topics.yaml`
- Create: `pytest.ini`

- [ ] **Step 1: Create package skeleton**

```bash
mkdir -p knowledge_tracker/sources knowledge_tracker/preferences \
         knowledge_tracker/generators knowledge_tracker/obsidian \
         tests/test_sources tests/fixtures \
         config .github/workflows
touch knowledge_tracker/__init__.py \
      knowledge_tracker/preferences/__init__.py \
      knowledge_tracker/generators/__init__.py \
      knowledge_tracker/obsidian/__init__.py
```

- [ ] **Step 2: Write `requirements.in`**

```
anthropic
praw
atproto
tavily-python
feedparser
httpx
beautifulsoup4
pyyaml
gitpython
sentence-transformers
torch
scikit-learn
apscheduler
pytest
pytest-asyncio
respx
```

- [ ] **Step 3: Install and pin deps**

```bash
pip install pip-tools
pip-compile requirements.in -o requirements.txt
pip install -r requirements.txt
```

Expected: `requirements.txt` created with pinned versions.

- [ ] **Step 4: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 5: Write `config/topics.yaml`**

```yaml
obsidian_vault:
  repo: "git@github.com:you/your-vault.git"
  local_path: "/path/to/local/vault"
  digests_folder: "Digests"
  deepdive_folder: "DeepDives"
  preferences_file: "preferences.md"

claude_model: "claude-sonnet-4-6"
web_search_provider: "tavily"
max_articles_per_digest: 20
max_articles_deepdive: 15
web_search_queries_per_article: 2
dedup_similarity_threshold: 0.85

topics:
  - name: "AI Engineering"
    slug: "ai_engineering"
    keywords: ["LLM", "RAG", "agent", "fine-tuning", "evals"]
    reference_links: []
    flag_tag: "#deepdive"
    sources:
      hackernews: true
      reddit:
        subreddits: ["MachineLearning", "LocalLLaMA"]
      bluesky:
        hashtags: ["#llm"]
        accounts: []
      github_trending:
        language: ""
      web_search: true
      feeds: []
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: project scaffolding and dependencies"
```

---

## Task 2: Models and config loader

**Files:**
- Create: `knowledge_tracker/models.py`
- Create: `knowledge_tracker/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for config loader**

```python
# tests/test_config.py
from knowledge_tracker.config import load_config

def test_load_config_returns_topics():
    cfg = load_config("config/topics.yaml")
    assert len(cfg["topics"]) >= 1
    assert cfg["topics"][0]["slug"] == "ai_engineering"

def test_load_config_defaults():
    cfg = load_config("config/topics.yaml")
    # flag_tag defaults to #deepdive if not set
    topic = cfg["topics"][0]
    assert topic.get("flag_tag", "#deepdive") == "#deepdive"

def test_load_config_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")

def test_load_config_fails_fast_missing_search_key(monkeypatch):
    """web_search_provider=tavily with no TAVILY_API_KEY env var raises at startup."""
    import os, pytest
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="TAVILY_API_KEY"):
        load_config("config/topics.yaml", validate_env=True)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Write `knowledge_tracker/models.py`**

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Article:
    url: str
    title: str
    description: str
    source: str                          # e.g. "hackernews", "reddit"
    author: Optional[str] = None
    score: int = 0                       # engagement score from source (HN points, upvotes)
    embedding: Optional[list[float]] = None
    merged_sources: list[str] = field(default_factory=list)  # other sources covering same story
    flagged_date: Optional[str] = None   # ISO date string, set by reader.py
```

- [ ] **Step 4: Write `knowledge_tracker/config.py`**

```python
import os
import yaml
from pathlib import Path


def load_config(path: str, validate_env: bool = False) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(p) as f:
        cfg = yaml.safe_load(f)

    # Apply flag_tag default per topic
    for topic in cfg.get("topics", []):
        topic.setdefault("flag_tag", "#deepdive")

    # Vault path: VAULT_PATH env var overrides local_path
    vault_env = os.environ.get("VAULT_PATH")
    if vault_env:
        cfg["obsidian_vault"]["local_path"] = vault_env

    if validate_env:
        _validate_env(cfg)

    return cfg


def _validate_env(cfg: dict) -> None:
    provider = cfg.get("web_search_provider", "tavily")
    key_map = {"tavily": "TAVILY_API_KEY", "exa": "EXA_API_KEY"}
    key = key_map.get(provider)
    if key and not os.environ.get(key):
        raise EnvironmentError(
            f"web_search_provider is '{provider}' but {key} env var is not set"
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY env var is not set")
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add knowledge_tracker/models.py knowledge_tracker/config.py tests/test_config.py
git commit -m "feat: Article model and config loader"
```

---

## Task 3: Source — base protocol + Hacker News

**Files:**
- Create: `knowledge_tracker/sources/__init__.py` (with submodule imports)
- Create: `knowledge_tracker/sources/base.py`
- Create: `knowledge_tracker/sources/hackernews.py`
- Create: `tests/test_sources/test_hackernews.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_sources/test_hackernews.py
import respx, httpx, pytest
from knowledge_tracker.sources.hackernews import fetch

MOCK_RESPONSE = {
    "hits": [
        {
            "objectID": "123",
            "title": "Understanding RAG",
            "url": "https://example.com/rag",
            "author": "alice",
            "points": 250,
            "story_text": None,
        }
    ]
}

@respx.mock
def test_fetch_returns_articles():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, json=MOCK_RESPONSE)
    )
    articles = fetch(keywords=["RAG", "LLM"])
    assert len(articles) == 1
    assert articles[0].title == "Understanding RAG"
    assert articles[0].source == "hackernews"
    assert articles[0].score == 250

@respx.mock
def test_fetch_returns_empty_on_api_failure():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(500)
    )
    articles = fetch(keywords=["RAG"])
    assert articles == []
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_sources/test_hackernews.py -v
```

- [ ] **Step 3: Write `knowledge_tracker/sources/__init__.py`**

```python
from knowledge_tracker.sources import (
    hackernews,
    reddit,
    web_scraper,
    web_search,
    github_trending,
    bluesky,
)
```

- [ ] **Step 4: Write `knowledge_tracker/sources/base.py`**

```python
from typing import Protocol
from knowledge_tracker.models import Article


class Source(Protocol):
    def fetch(self, **kwargs) -> list[Article]:
        ...
```

- [ ] **Step 4: Write `knowledge_tracker/sources/hackernews.py`**

```python
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
```

- [ ] **Step 5: Run — verify pass**

```bash
pytest tests/test_sources/test_hackernews.py -v
```

- [ ] **Step 6: Commit**

```bash
git add knowledge_tracker/sources/ tests/test_sources/test_hackernews.py
git commit -m "feat: HackerNews source"
```

---

## Task 4: Source — Reddit

**Files:**
- Create: `knowledge_tracker/sources/reddit.py`
- Create: `tests/test_sources/test_reddit.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_sources/test_reddit.py
from unittest.mock import MagicMock, patch
from knowledge_tracker.sources.reddit import fetch

def _make_post(title, url, score, author):
    post = MagicMock()
    post.title = title
    post.url = url
    post.score = score
    post.author.name = author
    post.selftext = ""
    return post

@patch("knowledge_tracker.sources.reddit.praw.Reddit")
def test_fetch_returns_articles(mock_reddit_cls):
    post = _make_post("RAG pipelines", "https://example.com/rag", 400, "bob")
    mock_reddit_cls.return_value.subreddit.return_value.hot.return_value = [post]
    articles = fetch(subreddits=["MachineLearning"], limit=10)
    assert len(articles) == 1
    assert articles[0].title == "RAG pipelines"
    assert articles[0].source == "reddit"

@patch("knowledge_tracker.sources.reddit.praw.Reddit")
def test_fetch_returns_empty_on_failure(mock_reddit_cls):
    mock_reddit_cls.side_effect = Exception("auth error")
    articles = fetch(subreddits=["MachineLearning"])
    assert articles == []
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_sources/test_reddit.py -v
```

- [ ] **Step 3: Write `knowledge_tracker/sources/reddit.py`**

```python
import logging, os
import praw
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def fetch(subreddits: list[str], limit: int = 25) -> list[Article]:
    try:
        reddit = praw.Reddit(
            client_id=os.environ["REDDIT_CLIENT_ID"],
            client_secret=os.environ["REDDIT_CLIENT_SECRET"],
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
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_sources/test_reddit.py -v
```

- [ ] **Step 5: Commit**

```bash
git add knowledge_tracker/sources/reddit.py tests/test_sources/test_reddit.py
git commit -m "feat: Reddit source"
```

---

## Task 5: Source — RSS/web scraper + GitHub Trending

**Files:**
- Create: `knowledge_tracker/sources/web_scraper.py`
- Create: `knowledge_tracker/sources/github_trending.py`
- Create: `tests/test_sources/test_web_scraper.py`
- Create: `tests/test_sources/test_github_trending.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sources/test_web_scraper.py
import respx, httpx
from knowledge_tracker.sources.web_scraper import fetch_feeds, fetch_url

ATOM_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Test Article</title>
    <link href="https://example.com/test"/>
    <summary>A summary</summary>
    <author><name>Alice</name></author>
  </entry>
</feed>"""

@respx.mock
def test_fetch_feeds_parses_atom():
    respx.get("https://example.com/feed").mock(
        return_value=httpx.Response(200, text=ATOM_FEED,
            headers={"content-type": "application/atom+xml"})
    )
    articles = fetch_feeds(["https://example.com/feed"])
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].source == "feed"

@respx.mock
def test_fetch_url_returns_text():
    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text="<html><body><p>Content</p></body></html>")
    )
    text = fetch_url("https://example.com/article")
    assert "Content" in text

@respx.mock
def test_fetch_url_returns_empty_on_failure():
    respx.get("https://example.com/fail").mock(
        return_value=httpx.Response(404)
    )
    text = fetch_url("https://example.com/fail")
    assert text == ""
```

```python
# tests/test_sources/test_github_trending.py
import respx, httpx
from knowledge_tracker.sources.github_trending import fetch

TRENDING_HTML = """
<html><body>
<article class="Box-row">
  <h2><a href="/owner/repo">owner / repo</a></h2>
  <p>A cool project</p>
  <span class="d-inline-block float-sm-right">123 stars today</span>
</article>
</body></html>"""

@respx.mock
def test_fetch_returns_repos():
    respx.get("https://github.com/trending").mock(
        return_value=httpx.Response(200, text=TRENDING_HTML)
    )
    articles = fetch(language="")
    assert len(articles) == 1
    assert "repo" in articles[0].title.lower()
    assert articles[0].source == "github_trending"
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_sources/test_web_scraper.py tests/test_sources/test_github_trending.py -v
```

- [ ] **Step 3: Write `knowledge_tracker/sources/web_scraper.py`**

```python
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
```

- [ ] **Step 4: Write `knowledge_tracker/sources/github_trending.py`**

```python
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
```

- [ ] **Step 5: Run — verify pass**

```bash
pytest tests/test_sources/test_web_scraper.py tests/test_sources/test_github_trending.py -v
```

- [ ] **Step 6: Commit**

```bash
git add knowledge_tracker/sources/web_scraper.py knowledge_tracker/sources/github_trending.py \
        tests/test_sources/
git commit -m "feat: RSS/web scraper and GitHub Trending sources"
```

---

## Task 6: Source — Bluesky + web search

**Files:**
- Create: `knowledge_tracker/sources/bluesky.py`
- Create: `knowledge_tracker/sources/web_search.py`
- Create: `tests/test_sources/test_bluesky.py`
- Create: `tests/test_sources/test_web_search.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sources/test_bluesky.py
from unittest.mock import MagicMock, patch
from knowledge_tracker.sources.bluesky import fetch

@patch("knowledge_tracker.sources.bluesky.Client")
def test_fetch_returns_articles(mock_client_cls):
    post = MagicMock()
    post.post.record.text = "Great article on RAG https://example.com/rag"
    post.post.author.handle = "alice.bsky.social"
    post.post.uri = "at://alice/post/1"
    mock_client_cls.return_value.app.bsky.feed.search_posts.return_value.feed = [post]
    articles = fetch(hashtags=["#llm"], accounts=[], handle="test", password="test")
    assert len(articles) >= 1
    assert articles[0].source == "bluesky"

@patch("knowledge_tracker.sources.bluesky.Client")
def test_fetch_returns_empty_on_failure(mock_client_cls):
    mock_client_cls.side_effect = Exception("auth")
    articles = fetch(hashtags=["#llm"], accounts=[], handle="h", password="p")
    assert articles == []
```

```python
# tests/test_sources/test_web_search.py
import respx, httpx, os, pytest
from knowledge_tracker.sources.web_search import fetch

TAVILY_RESPONSE = {
    "results": [{"url": "https://example.com", "title": "RAG Guide", "content": "summary"}]
}

@respx.mock
def test_fetch_tavily(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(200, json=TAVILY_RESPONSE)
    )
    articles = fetch(query="RAG LLM", provider="tavily", max_results=5)
    assert len(articles) == 1
    assert articles[0].source == "web_search"

@respx.mock
def test_fetch_returns_empty_on_failure(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(500)
    )
    articles = fetch(query="RAG", provider="tavily")
    assert articles == []
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_sources/test_bluesky.py tests/test_sources/test_web_search.py -v
```

- [ ] **Step 3: Write `knowledge_tracker/sources/bluesky.py`**

```python
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
```

- [ ] **Step 4: Write `knowledge_tracker/sources/web_search.py`**

```python
import logging, os
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def fetch(query: str, provider: str = "tavily", max_results: int = 10) -> list[Article]:
    if provider == "tavily":
        return _fetch_tavily(query, max_results)
    elif provider == "exa":
        return _fetch_exa(query, max_results)
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


def _fetch_exa(query: str, max_results: int) -> list[Article]:
    api_key = os.environ.get("EXA_API_KEY", "")
    try:
        resp = httpx.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key},
            json={"query": query, "numResults": max_results, "useAutoprompt": True},
            timeout=15,
        )
        resp.raise_for_status()
        return [
            Article(url=r["url"], title=r.get("title", ""), description=r.get("text", "")[:500],
                    source="web_search", score=0)
            for r in resp.json().get("results", [])
        ]
    except Exception as e:
        logger.warning("Exa search failed: %s", e)
        return []
```

- [ ] **Step 5: Run — verify pass**

```bash
pytest tests/test_sources/test_bluesky.py tests/test_sources/test_web_search.py -v
```

- [ ] **Step 6: Commit**

```bash
git add knowledge_tracker/sources/bluesky.py knowledge_tracker/sources/web_search.py \
        tests/test_sources/
git commit -m "feat: Bluesky and web search sources"
```

---

## Task 7: Deduplication (URL + semantic)

**Files:**
- Create: `knowledge_tracker/dedup.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dedup.py
from knowledge_tracker.models import Article
from knowledge_tracker.dedup import url_dedup, semantic_dedup

def make_article(url, title, desc="", score=0, source="hn"):
    return Article(url=url, title=title, description=desc, source=source, score=score)

def test_url_dedup_removes_duplicates():
    articles = [
        make_article("https://example.com/a", "Article A", score=100, source="hackernews"),
        make_article("https://example.com/a", "Article A", score=50, source="reddit"),
        make_article("https://example.com/b", "Article B"),
    ]
    result = url_dedup(articles)
    assert len(result) == 2
    # higher-score source kept
    a = next(r for r in result if r.url == "https://example.com/a")
    assert a.score == 100
    assert "reddit" in a.merged_sources

def test_url_dedup_preserves_unique():
    articles = [make_article("https://a.com", "A"), make_article("https://b.com", "B")]
    assert len(url_dedup(articles)) == 2

def test_semantic_dedup_clusters_similar():
    # Two very similar titles should be clustered
    articles = [
        make_article("https://a.com", "Introduction to RAG systems for LLMs", score=100),
        make_article("https://b.com", "Getting started with RAG for large language models", score=50),
        make_article("https://c.com", "How to cook pasta at home", score=200),
    ]
    result = semantic_dedup(articles, threshold=0.80)
    # pasta article must survive; RAG pair should be 1
    urls = {r.url for r in result}
    assert "https://c.com" in urls
    assert len(result) == 2  # RAG pair clustered into one

def test_semantic_dedup_keeps_highest_score_representative():
    articles = [
        make_article("https://a.com", "RAG retrieval augmented generation tutorial", score=50),
        make_article("https://b.com", "RAG retrieval augmented generation guide", score=200),
    ]
    result = semantic_dedup(articles, threshold=0.80)
    assert len(result) == 1
    assert result[0].score == 200
    assert "https://a.com" in result[0].merged_sources or result[0].url == "https://b.com"
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_dedup.py -v
```

- [ ] **Step 3: Write `knowledge_tracker/dedup.py`**

```python
import logging
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def url_dedup(articles: list[Article]) -> list[Article]:
    """Deduplicate by exact URL. Keep highest-score; record merged sources."""
    seen: dict[str, Article] = {}
    for article in articles:
        url = article.url
        if url not in seen:
            seen[url] = article
        else:
            existing = seen[url]
            if article.score > existing.score:
                article.merged_sources = existing.merged_sources + [existing.source]
                seen[url] = article
            else:
                existing.merged_sources.append(article.source)
    return list(seen.values())


def semantic_dedup(articles: list[Article], threshold: float = 0.85) -> list[Article]:
    """Cluster semantically similar articles; keep highest-score representative."""
    if len(articles) <= 1:
        return articles

    model = _get_model()
    texts = [f"{a.title} {a.description}"[:512] for a in articles]
    embeddings = model.encode(texts, normalize_embeddings=True)

    # Store embeddings on articles for reuse in scorer
    for article, emb in zip(articles, embeddings):
        article.embedding = emb.tolist()

    sim_matrix = cosine_similarity(embeddings)
    n = len(articles)
    visited = [False] * n
    clusters: list[list[int]] = []

    for i in range(n):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if not visited[j] and sim_matrix[i][j] >= threshold:
                cluster.append(j)
                visited[j] = True
        clusters.append(cluster)

    result = []
    for cluster in clusters:
        best_idx = max(cluster, key=lambda i: articles[i].score)
        rep = articles[best_idx]
        for idx in cluster:
            if idx != best_idx:
                rep.merged_sources.append(articles[idx].url)
        result.append(rep)

    return result
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_dedup.py -v
```

- [ ] **Step 5: Commit**

```bash
git add knowledge_tracker/dedup.py tests/test_dedup.py
git commit -m "feat: URL and semantic deduplication"
```

---

## Task 8: Preferences store + scorer

**Files:**
- Create: `knowledge_tracker/preferences/store.py`
- Create: `knowledge_tracker/preferences/scorer.py`
- Create: `tests/test_store.py`
- Create: `tests/test_scorer.py`
- Create: `tests/fixtures/sample_preferences.md`

- [ ] **Step 1: Write fixture and failing tests**

```markdown
<!-- tests/fixtures/sample_preferences.md -->
---
updated: 2026-03-21
topics:
  ai_engineering:
    preferred_domains: ["eugeneyan.com"]
    preferred_authors: ["alice"]
    positive_keywords: ["RAG", "evals"]
    negative_keywords: ["crypto"]
    reference_links: []
---

# My Reading Preferences

Auto-updated weekly from flagged articles. Edit manually to tune.
```

```python
# tests/test_store.py
import os, tempfile, shutil
from knowledge_tracker.models import Article
from knowledge_tracker.preferences.store import update_preferences, load_preferences

def setup_vault(tmp_dir):
    prefs_path = os.path.join(tmp_dir, "preferences.md")
    shutil.copy("tests/fixtures/sample_preferences.md", prefs_path)
    return prefs_path

def test_load_preferences_parses_frontmatter(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    shutil.copy("tests/fixtures/sample_preferences.md", prefs_file)
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert "eugeneyan.com" in prefs["preferred_domains"]
    assert "RAG" in prefs["positive_keywords"]

def test_load_preferences_returns_none_when_missing(tmp_path):
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert prefs is None

def test_update_preferences_merges_new_domains(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    shutil.copy("tests/fixtures/sample_preferences.md", prefs_file)
    articles = [Article(url="https://newdomain.com/article", title="T", description="D", source="hn")]
    phase1 = [{"keywords": ["agents", "RAG"]}]
    update_preferences(str(tmp_path), "preferences.md", "ai_engineering", phase1, articles)
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert "newdomain.com" in prefs["preferred_domains"]

def test_update_preferences_deduplicates(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    shutil.copy("tests/fixtures/sample_preferences.md", prefs_file)
    articles = [Article(url="https://eugeneyan.com/post", title="T", description="D", source="hn")]
    phase1 = [{"keywords": ["RAG"]}]
    update_preferences(str(tmp_path), "preferences.md", "ai_engineering", phase1, articles)
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert prefs["preferred_domains"].count("eugeneyan.com") == 1

def test_update_preferences_nonfatal_on_bad_yaml(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    prefs_file.write_text("---\nbad: [yaml: nonsense\n---\nbody\n")
    # Should not raise
    update_preferences(str(tmp_path), "preferences.md", "ai_engineering", [], [])
```

```python
# tests/test_scorer.py
from unittest.mock import MagicMock
from knowledge_tracker.models import Article
from knowledge_tracker.preferences.scorer import score_and_filter

def make_article(url, title, desc="", author=None, score=0):
    return Article(url=url, title=title, description=desc, source="hn",
                   author=author, score=score)

def make_embedder(return_val=None):
    embedder = MagicMock()
    import numpy as np
    embedder.encode.return_value = np.array([[1.0, 0.0]] * 10)
    return embedder

def test_filters_negative_keyword_articles():
    articles = [
        make_article("https://a.com", "Great RAG article"),
        make_article("https://b.com", "Bitcoin crypto scam"),
    ]
    prefs = {"preferred_domains": [], "preferred_authors": [],
             "positive_keywords": ["RAG"], "negative_keywords": ["crypto"],
             "reference_links": []}
    topic = {"keywords": ["RAG"], "reference_links": []}
    embedder = make_embedder()
    result = score_and_filter(articles, topic, prefs, embedder, max_results=10)
    urls = {r.url for r in result}
    assert "https://b.com" not in urls

def test_preferred_domain_boosts_score():
    articles = [
        make_article("https://eugeneyan.com/post", "RAG article"),
        make_article("https://unknown.com/post", "RAG article"),
    ]
    prefs = {"preferred_domains": ["eugeneyan.com"], "preferred_authors": [],
             "positive_keywords": [], "negative_keywords": [], "reference_links": []}
    topic = {"keywords": ["RAG"], "reference_links": []}
    embedder = make_embedder()
    result = score_and_filter(articles, topic, prefs, embedder, max_results=10)
    assert result[0].url == "https://eugeneyan.com/post"

def test_caps_at_max_results():
    articles = [make_article(f"https://{i}.com", "RAG topic") for i in range(20)]
    topic = {"keywords": ["RAG"], "reference_links": []}
    embedder = make_embedder()
    result = score_and_filter(articles, topic, None, embedder, max_results=5)
    assert len(result) <= 5
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_store.py tests/test_scorer.py -v
```

- [ ] **Step 3: Write `knowledge_tracker/preferences/store.py`**

```python
import logging
import os
import re
from urllib.parse import urlparse
import yaml
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)


def load_preferences(vault_path: str, prefs_file: str, topic_slug: str) -> dict | None:
    path = os.path.join(vault_path, prefs_file)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            content = f.read()
        m = FRONTMATTER_RE.match(content)
        if not m:
            return None
        data = yaml.safe_load(m.group(1))
        return data.get("topics", {}).get(topic_slug)
    except Exception as e:
        logger.warning("Failed to load preferences: %s", e)
        return None


def update_preferences(
    vault_path: str,
    prefs_file: str,
    topic_slug: str,
    phase1_outputs: list[dict],
    articles: list[Article],
) -> None:
    path = os.path.join(vault_path, prefs_file)
    try:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            m = FRONTMATTER_RE.match(content)
            body = content[m.end():] if m else "\n# My Reading Preferences\n\nAuto-updated weekly.\n"
            data = yaml.safe_load(m.group(1)) if m else {}
        else:
            data = {}
            body = "\n# My Reading Preferences\n\nAuto-updated weekly.\n"

        data.setdefault("topics", {})
        data["topics"].setdefault(topic_slug, {
            "preferred_domains": [], "preferred_authors": [],
            "positive_keywords": [], "negative_keywords": [], "reference_links": [],
        })
        topic_prefs = data["topics"][topic_slug]

        # Extract domains
        for article in articles:
            domain = urlparse(article.url).netloc.lstrip("www.")
            if domain and domain not in topic_prefs["preferred_domains"]:
                topic_prefs["preferred_domains"].append(domain)

        # Extract authors
        for article in articles:
            if article.author and article.author not in topic_prefs["preferred_authors"]:
                topic_prefs["preferred_authors"].append(article.author)

        # Extract keywords from Phase 1
        for output in phase1_outputs:
            for kw in output.get("keywords", []):
                if kw and kw not in topic_prefs["positive_keywords"]:
                    topic_prefs["positive_keywords"].append(kw)

        import datetime
        data["updated"] = datetime.date.today().isoformat()
        new_frontmatter = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        with open(path, "w") as f:
            f.write(f"---\n{new_frontmatter}---\n{body}")

    except Exception as e:
        logger.error("Failed to update preferences.md (non-fatal): %s", e)
```

- [ ] **Step 4: Write `knowledge_tracker/preferences/scorer.py`**

```python
import logging
import numpy as np
from urllib.parse import urlparse
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def score_and_filter(
    articles: list[Article],
    topic_config: dict,
    preferences: dict | None,
    embedder: SentenceTransformer,
    max_results: int,
) -> list[Article]:
    prefs = preferences or {}
    preferred_domains = set(prefs.get("preferred_domains", []))
    preferred_authors = set(prefs.get("preferred_authors", []))
    positive_keywords = prefs.get("positive_keywords", [])
    negative_keywords = prefs.get("negative_keywords", [])
    ref_domains = {
        urlparse(u).netloc.lstrip("www.")
        for u in (topic_config.get("reference_links", []) + prefs.get("reference_links", []))
        if u
    }

    # Build topic vector text
    topic_text = " ".join(topic_config.get("keywords", []) + positive_keywords)
    topic_vec = embedder.encode([topic_text], normalize_embeddings=True)

    # Embed articles (reuse if already set)
    for article in articles:
        if article.embedding is None:
            text = f"{article.title} {article.description}"[:512]
            article.embedding = embedder.encode([text], normalize_embeddings=True)[0].tolist()

    scored = []
    for article in articles:
        article_vec = np.array(article.embedding).reshape(1, -1)
        sim = float(cosine_similarity(topic_vec, article_vec)[0][0])
        semantic_score = sim * 60  # 0–60

        structural = 0.0
        domain = urlparse(article.url).netloc.lstrip("www.")
        if domain in preferred_domains:
            structural += 15
        if article.author and article.author in preferred_authors:
            structural += 15
        if domain in ref_domains:
            structural += 10
        text = f"{article.title} {article.description}".lower()
        for kw in negative_keywords:
            if kw.lower() in text:
                structural -= 25

        total = max(-100.0, min(100.0, semantic_score + structural))
        scored.append((total, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for score, a in scored if score > 0][:max_results]
```

- [ ] **Step 5: Run — verify pass**

```bash
pytest tests/test_store.py tests/test_scorer.py -v
```

- [ ] **Step 6: Commit**

```bash
git add knowledge_tracker/preferences/ tests/test_store.py tests/test_scorer.py \
        tests/fixtures/sample_preferences.md
git commit -m "feat: preferences store and semantic scorer"
```

---

## Task 9: Obsidian reader + writer + git_sync

**Files:**
- Create: `knowledge_tracker/obsidian/reader.py`
- Create: `knowledge_tracker/obsidian/writer.py`
- Create: `knowledge_tracker/obsidian/git_sync.py`
- Create: `tests/test_reader.py`
- Create: `tests/test_writer.py`
- Create: `tests/fixtures/sample_digest.md`

- [ ] **Step 1: Write fixture and failing tests**

```markdown
<!-- tests/fixtures/sample_digest.md -->
---
date: 2026-03-19
topic: AI Engineering
sources_fetched: [hackernews]
sources_failed: []
---

# AI Engineering — Daily Digest · 2026-03-19

## Top Stories

### [RAG is Great](https://example.com/rag)
*Source: Hacker News · 300 points*
A good article about RAG.

#deepdive

---

### [Another Article](https://example.com/other)
*Source: Hacker News · 50 points*
Not flagged.

---

## Manual Links
<!-- Add links here -->
- https://manual.com/link1
- [Custom Title](https://manual.com/link2)
-
```

```python
# tests/test_reader.py
import shutil
from pathlib import Path
from knowledge_tracker.obsidian.reader import parse_digest_file, parse_week_digests

def test_parse_digest_file_finds_flagged(tmp_path):
    shutil.copy("tests/fixtures/sample_digest.md", tmp_path / "2026-03-19.md")
    flagged, manual = parse_digest_file(str(tmp_path / "2026-03-19.md"), flag_tag="#deepdive")
    assert len(flagged) == 1
    assert flagged[0].url == "https://example.com/rag"
    assert flagged[0].flagged_date == "2026-03-19"

def test_parse_digest_file_finds_manual_links(tmp_path):
    shutil.copy("tests/fixtures/sample_digest.md", tmp_path / "2026-03-19.md")
    flagged, manual = parse_digest_file(str(tmp_path / "2026-03-19.md"), flag_tag="#deepdive")
    assert len(manual) == 2
    assert any("manual.com/link1" in m.url for m in manual)
    assert any("manual.com/link2" in m.url for m in manual)

def test_parse_digest_file_ignores_empty_manual_lines(tmp_path):
    shutil.copy("tests/fixtures/sample_digest.md", tmp_path / "2026-03-19.md")
    _, manual = parse_digest_file(str(tmp_path / "2026-03-19.md"), flag_tag="#deepdive")
    # bare "-" lines must be excluded
    assert all(m.url for m in manual)

def test_parse_week_digests_deduplicates_by_url(tmp_path):
    digest_dir = tmp_path / "digests"
    digest_dir.mkdir()
    # Same file copied to two different days
    shutil.copy("tests/fixtures/sample_digest.md", digest_dir / "2026-03-18.md")
    shutil.copy("tests/fixtures/sample_digest.md", digest_dir / "2026-03-19.md")
    articles = parse_week_digests(str(digest_dir), "2026-03-16", "2026-03-22", "#deepdive")
    urls = [a.url for a in articles]
    assert urls.count("https://example.com/rag") == 1
```

```python
# tests/test_writer.py
import os
from knowledge_tracker.obsidian.writer import write_digest, write_deepdive

def test_write_digest_creates_file(tmp_path):
    vault = tmp_path / "vault"
    (vault / "Digests" / "ai_engineering").mkdir(parents=True)
    write_digest(
        vault_path=str(vault),
        folder="Digests",
        topic_slug="ai_engineering",
        date="2026-03-21",
        frontmatter={"topic": "AI Engineering", "sources_fetched": ["hackernews"], "sources_failed": []},
        body="## Top Stories\n\n### [Article](https://example.com)\nSummary.",
    )
    path = vault / "Digests" / "ai_engineering" / "2026-03-21.md"
    assert path.exists()
    content = path.read_text()
    assert "AI Engineering" in content
    assert "## Manual Links" in content

def test_write_deepdive_creates_file(tmp_path):
    vault = tmp_path / "vault"
    (vault / "DeepDives" / "ai_engineering").mkdir(parents=True)
    write_deepdive(
        vault_path=str(vault),
        folder="DeepDives",
        topic_slug="ai_engineering",
        week_start="2026-03-16",
        frontmatter={"topic": "AI Engineering", "articles_reviewed": 3},
        body="## Article Deep Dives\n...\n## Synthesis\n...",
    )
    path = vault / "DeepDives" / "ai_engineering" / "2026-03-16-week.md"
    assert path.exists()
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_reader.py tests/test_writer.py -v
```

- [ ] **Step 3: Write `knowledge_tracker/obsidian/reader.py`**

```python
import logging
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
MD_LINK_RE = re.compile(r'\[([^\]]*)\]\((https?://[^\)]+)\)')
BARE_URL_RE = re.compile(r'https?://\S+')


def parse_digest_file(filepath: str, flag_tag: str = "#deepdive") -> tuple[list[Article], list[Article]]:
    flagged, manual = [], []
    tag_re = re.compile(r'(?<!\S)' + re.escape(flag_tag) + r'(?!\S)')
    file_date = Path(filepath).stem  # "2026-03-19"

    try:
        with open(filepath) as f:
            content = f.read()
    except Exception as e:
        logger.warning("Failed to read digest %s: %s", filepath, e)
        return [], []

    # ── Flagged articles ──────────────────────────────────────
    # Split into sections at ### headings, ## headings, or --- separators
    section_re = re.compile(r'(?=^#{2,3} |\n---\n)', re.MULTILINE)
    sections = section_re.split(content)

    for section in sections:
        if not section.startswith("###"):
            continue
        if not tag_re.search(section):
            continue
        heading_line = section.split("\n")[0]
        m = MD_LINK_RE.search(heading_line)
        if m:
            flagged.append(Article(
                url=m.group(2), title=m.group(1),
                description="", source="digest", flagged_date=file_date,
            ))

    # ── Manual links ──────────────────────────────────────────
    manual_match = re.search(r'## Manual Links\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if manual_match:
        for line in manual_match.group(1).split("\n"):
            line = line.strip().lstrip("- ").strip()
            if not line or line.startswith("<!--"):
                continue
            m = MD_LINK_RE.search(line)
            if m:
                manual.append(Article(url=m.group(2), title=m.group(1),
                                      description="", source="manual", flagged_date=file_date))
            else:
                url_m = BARE_URL_RE.search(line)
                if url_m:
                    manual.append(Article(url=url_m.group(), title="",
                                          description="", source="manual", flagged_date=file_date))

    return flagged, manual


def parse_week_digests(
    digest_dir: str,
    week_start: str,
    week_end: str,
    flag_tag: str = "#deepdive",
) -> list[Article]:
    from datetime import date as date_cls
    start = date_cls.fromisoformat(week_start)
    end = date_cls.fromisoformat(week_end)

    all_articles: dict[str, Article] = {}
    for f in sorted(Path(digest_dir).glob("*.md")):
        try:
            file_date = date_cls.fromisoformat(f.stem)
        except ValueError:
            continue
        if not (start <= file_date <= end):
            continue
        flagged, manual = parse_digest_file(str(f), flag_tag)
        for article in flagged + manual:
            if article.url not in all_articles:
                all_articles[article.url] = article

    return list(all_articles.values())
```

- [ ] **Step 4: Write `knowledge_tracker/obsidian/writer.py`**

```python
import os
from datetime import date


def write_digest(
    vault_path: str,
    folder: str,
    topic_slug: str,
    date: str,
    frontmatter: dict,
    body: str,
) -> str:
    import yaml
    dir_path = os.path.join(vault_path, folder, topic_slug)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{date}.md")

    fm = yaml.dump({"date": date, **frontmatter}, default_flow_style=False, allow_unicode=True)
    manual_section = "\n## Manual Links\n<!-- Add links here for weekly deep dive inclusion -->\n<!-- Format: - [optional title](url) or bare URL on its own line -->\n-\n"
    content = f"---\n{fm}---\n\n{body}\n{manual_section}"

    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def write_deepdive(
    vault_path: str,
    folder: str,
    topic_slug: str,
    week_start: str,
    frontmatter: dict,
    body: str,
) -> str:
    import yaml
    dir_path = os.path.join(vault_path, folder, topic_slug)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{week_start}-week.md")

    fm = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    content = f"---\n{fm}---\n\n{body}\n"

    with open(filepath, "w") as f:
        f.write(content)
    return filepath
```

- [ ] **Step 5: Write `knowledge_tracker/obsidian/git_sync.py`**

```python
import logging
import git

logger = logging.getLogger(__name__)


class GitSyncError(Exception):
    pass


def sync_vault(vault_path: str, commit_message: str) -> None:
    """Pull latest, stage all, commit if changed, push. Local runs only."""
    try:
        repo = git.Repo(vault_path)
        repo.remotes.origin.pull(rebase=True)
        repo.git.add(A=True)
        if repo.is_dirty(index=True):
            repo.index.commit(commit_message)
            repo.remotes.origin.push()
            logger.info("Vault synced: %s", commit_message)
        else:
            logger.info("No changes to commit.")
    except git.GitCommandError as e:
        raise GitSyncError(f"Git sync failed: {e}") from e
```

- [ ] **Step 6: Run — verify pass**

```bash
pytest tests/test_reader.py tests/test_writer.py -v
```

- [ ] **Step 7: Commit**

```bash
git add knowledge_tracker/obsidian/ tests/test_reader.py tests/test_writer.py \
        tests/fixtures/sample_digest.md tests/fixtures/sample_preferences.md
git commit -m "feat: obsidian reader, writer, and git_sync"
```

---

## Task 10: Claude client with retry

**Files:**
- Create: `knowledge_tracker/claude_client.py`

- [ ] **Step 1: Write the module** (no unit test — wraps external API; tested via integration)

```python
import logging
import time
import os
import anthropic

logger = logging.getLogger(__name__)
MAX_RETRIES = 3
BACKOFF = [1, 2, 4]


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def chat(
    messages: list[dict],
    model: str,
    system: str = "",
    max_tokens: int = 4096,
    tools: list[dict] | None = None,
) -> str | dict:
    """
    Call Claude with retry. Returns text string for regular calls,
    or parsed tool_use content dict for structured output calls.
    Raises RuntimeError after MAX_RETRIES failures.
    """
    client = get_client()
    kwargs = dict(model=model, messages=messages, max_tokens=max_tokens)
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = {"type": "any"}

    last_err = None
    for attempt, delay in enumerate(BACKOFF):
        try:
            response = client.messages.create(**kwargs)
            if tools:
                for block in response.content:
                    if block.type == "tool_use":
                        return block.input
                raise RuntimeError("No tool_use block in response")
            return response.content[0].text
        except anthropic.RateLimitError as e:
            wait = int(e.response.headers.get("Retry-After", delay))
            logger.warning("Rate limited, waiting %ss (attempt %d)", wait, attempt + 1)
            time.sleep(wait)
            last_err = e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                logger.warning("Claude server error %s, retrying in %ss", e.status_code, delay)
                time.sleep(delay)
                last_err = e
            else:
                raise
        except Exception as e:
            raise

    raise RuntimeError(f"Claude API failed after {len(BACKOFF)} attempts: {last_err}")
```

- [ ] **Step 2: Commit**

```bash
git add knowledge_tracker/claude_client.py
git commit -m "feat: Claude API client with exponential backoff retry"
```

---

## Task 11: Daily digest generator

**Files:**
- Create: `knowledge_tracker/generators/digest.py`

- [ ] **Step 1: Write the module**

```python
import logging
from knowledge_tracker.models import Article
from knowledge_tracker import claude_client

logger = logging.getLogger(__name__)

DIGEST_TOOL = {
    "name": "write_digest",
    "description": "Write the digest markdown body for a set of articles.",
    "input_schema": {
        "type": "object",
        "properties": {
            "body": {
                "type": "string",
                "description": "Full markdown body of the digest (no frontmatter). "
                               "Start with ## Top Stories, use ### for each article."
            }
        },
        "required": ["body"]
    }
}

SYSTEM = """You are a concise, neutral knowledge curator.
Write a daily digest from the provided articles.
Group thematically if natural. 2-3 sentence summary per article.
Do not editorialize. Use the write_digest tool."""


def generate(
    articles: list[Article],
    topic_name: str,
    date: str,
    model: str,
) -> str:
    """Returns the markdown body string for the digest."""
    if not articles:
        return "## Top Stories\n\n*No articles found today.*\n"

    article_list = "\n\n".join(
        f"Title: {a.title}\nURL: {a.url}\nSource: {a.source}"
        + (f" (also: {', '.join(a.merged_sources)})" if a.merged_sources else "")
        + f"\nSnippet: {a.description[:300]}"
        for a in articles
    )

    messages = [{
        "role": "user",
        "content": f"Topic: {topic_name}\nDate: {date}\n\nArticles:\n\n{article_list}"
    }]

    try:
        result = claude_client.chat(messages, model=model, system=SYSTEM, tools=[DIGEST_TOOL])
        return result.get("body", "## Top Stories\n\n*Generation failed.*\n")
    except Exception as e:
        logger.error("Digest generation failed: %s", e)
        return f"## Error\n\nDigest generation failed — {e}\n"
```

- [ ] **Step 2: Commit**

```bash
git add knowledge_tracker/generators/digest.py
git commit -m "feat: daily digest generator"
```

---

## Task 12: Weekly deep dive generator

**Files:**
- Create: `knowledge_tracker/generators/deepdive.py`

- [ ] **Step 1: Write the module**

```python
import logging
from knowledge_tracker.models import Article
from knowledge_tracker import claude_client

logger = logging.getLogger(__name__)
CHAR_LIMIT = 320_000  # ~80k tokens at 4 chars/token

PHASE1_TOOL = {
    "name": "article_analysis",
    "description": "Structured deep dive analysis of a single article.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_insights": {"type": "array", "items": {"type": "string"}},
            "research_expansion": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"},
                         "description": "3-5 topical keywords"},
        },
        "required": ["summary", "key_insights", "research_expansion", "keywords"]
    }
}

PHASE1_SYSTEM = "You are a research analyst. Analyse the article and related search results using the article_analysis tool."

PHASE2_SYSTEM = """You are a synthesis expert. Given per-article analyses, write:
1. Cross-article themes and patterns (## Synthesis section)
2. Practical action steps the reader can take (## Practical Action Steps section)
Ground your action steps in the user's focus areas."""


def analyse_article(
    article: Article,
    full_content: str,
    search_results: list[str],
    model: str,
) -> dict:
    content = full_content[:CHAR_LIMIT]
    search_text = "\n\n".join(search_results)
    messages = [{
        "role": "user",
        "content": f"Title: {article.title}\nURL: {article.url}\n\n"
                   f"Article content:\n{content}\n\n"
                   f"Related search results:\n{search_text}"
    }]
    try:
        return claude_client.chat(messages, model=model, system=PHASE1_SYSTEM, tools=[PHASE1_TOOL])
    except Exception as e:
        logger.error("Phase 1 failed for %s: %s", article.url, e)
        return {"summary": f"Analysis failed: {e}", "key_insights": [],
                "research_expansion": "", "keywords": []}


def synthesise(
    phase1_outputs: list[dict],
    articles: list[Article],
    topic_keywords: list[str],
    preferences: dict | None,
    model: str,
) -> str:
    focus = topic_keywords + (preferences or {}).get("positive_keywords", [])
    summaries = []
    for article, output in zip(articles, phase1_outputs):
        summaries.append(
            f"### {article.title}\n"
            f"**Summary:** {output.get('summary', '')}\n"
            f"**Key Insights:**\n" + "\n".join(f"- {i}" for i in output.get("key_insights", [])) +
            f"\n**Research Expansion:** {output.get('research_expansion', '')}"
        )
    combined = "\n\n---\n\n".join(summaries)
    messages = [{
        "role": "user",
        "content": f"User focus areas: {', '.join(focus)}\n\n"
                   f"Article analyses:\n\n{combined}"
    }]
    try:
        return claude_client.chat(messages, model=model, system=PHASE2_SYSTEM, max_tokens=4096)
    except Exception as e:
        logger.error("Phase 2 synthesis failed: %s", e)
        return f"## Synthesis\n\n*Synthesis failed: {e}*\n"


def format_deepdive_body(
    articles: list[Article],
    phase1_outputs: list[dict],
    synthesis: str,
    skipped_urls: list[str],
) -> str:
    lines = []
    if skipped_urls:
        lines.append(f"> Note: {len(skipped_urls)} articles were skipped (limit reached):\n"
                     + "\n".join(f"> - {u}" for u in skipped_urls))
        lines.append("")

    lines.append("## Article Deep Dives\n")
    for i, (article, output) in enumerate(zip(articles, phase1_outputs), 1):
        lines.append(f"### {i}. [{article.title}]({article.url})")
        lines.append(f"**Source:** {article.source}" +
                     (f" · flagged {article.flagged_date}" if article.flagged_date else ""))
        lines.append(f"\n**Summary:** {output.get('summary', '')}")
        lines.append("\n**Key Insights:**")
        for insight in output.get("key_insights", []):
            lines.append(f"- {insight}")
        lines.append(f"\n**Research Expansion:** {output.get('research_expansion', '')}")
        lines.append("\n---\n")

    lines.append(synthesis)
    return "\n".join(lines)
```

- [ ] **Step 2: Commit**

```bash
git add knowledge_tracker/generators/deepdive.py
git commit -m "feat: weekly deep dive generator"
```

---

## Task 13: `run.py` — CLI orchestration

**Files:**
- Create: `run.py`

- [ ] **Step 1: Write `run.py`**

```python
#!/usr/bin/env python3
"""
Usage:
  python run.py daily [--topic NAME]
  python run.py weekly [--topic NAME]
"""
import argparse
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from sentence_transformers import SentenceTransformer

from knowledge_tracker.config import load_config
from knowledge_tracker.dedup import url_dedup, semantic_dedup
from knowledge_tracker.preferences.store import load_preferences, update_preferences
from knowledge_tracker.preferences.scorer import score_and_filter
from knowledge_tracker.obsidian.writer import write_digest, write_deepdive
from knowledge_tracker.obsidian.reader import parse_week_digests
from knowledge_tracker.obsidian.git_sync import sync_vault
from knowledge_tracker.generators import digest as digest_gen
from knowledge_tracker.generators import deepdive as deepdive_gen
from knowledge_tracker import sources

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run")

IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def _fetch_all_sources(topic: dict, cfg: dict) -> list:
    src_cfg = topic.get("sources", {})
    keywords = topic.get("keywords", [])
    vault = cfg["obsidian_vault"]
    bluesky_handle = os.environ.get("BLUESKY_HANDLE", "")
    bluesky_password = os.environ.get("BLUESKY_PASSWORD", "")

    tasks = []
    if src_cfg.get("hackernews"):
        tasks.append(("hackernews", lambda: sources.hackernews.fetch(keywords)))
    if src_cfg.get("reddit"):
        tasks.append(("reddit", lambda: sources.reddit.fetch(
            src_cfg["reddit"]["subreddits"])))
    if src_cfg.get("feeds"):
        tasks.append(("feeds", lambda: sources.web_scraper.fetch_feeds(src_cfg["feeds"])))
    if src_cfg.get("github_trending"):
        lang = src_cfg["github_trending"].get("language", "")
        tasks.append(("github_trending", lambda l=lang: sources.github_trending.fetch(l)))
    if src_cfg.get("bluesky") and bluesky_handle:
        bsky = src_cfg["bluesky"]
        tasks.append(("bluesky", lambda: sources.bluesky.fetch(
            bsky.get("hashtags", []), bsky.get("accounts", []),
            bluesky_handle, bluesky_password)))
    if src_cfg.get("web_search"):
        query = " ".join(keywords)
        provider = cfg.get("web_search_provider", "tavily")
        tasks.append(("web_search", lambda q=query, p=provider: sources.web_search.fetch(q, p)))

    results = []
    failed = []
    with ThreadPoolExecutor() as pool:
        futures = {pool.submit(fn): name for name, fn in tasks}
        for future, name in futures.items():
            try:
                results.extend(future.result())
            except Exception as e:
                logger.warning("Source %s failed: %s", name, e)
                failed.append(name)

    return results, failed


def run_daily(cfg: dict, topic_filter: str | None, embedder: SentenceTransformer):
    today = date.today().isoformat()
    vault = cfg["obsidian_vault"]

    for topic in cfg["topics"]:
        if topic_filter and topic["name"] != topic_filter:
            continue
        logger.info("Running daily digest for: %s", topic["name"])

        prefs = load_preferences(vault["local_path"], vault["preferences_file"], topic["slug"])
        articles, failed = _fetch_all_sources(topic, cfg)
        articles = url_dedup(articles)
        articles = semantic_dedup(articles, cfg.get("dedup_similarity_threshold", 0.85))
        articles = score_and_filter(articles, topic, prefs, embedder,
                                    cfg.get("max_articles_per_digest", 20))

        body = digest_gen.generate(articles, topic["name"], today, cfg["claude_model"])
        write_digest(
            vault_path=vault["local_path"],
            folder=vault["digests_folder"],
            topic_slug=topic["slug"],
            date=today,
            frontmatter={
                "topic": topic["name"],
                "sources_fetched": [k for k in topic.get("sources", {}) if k not in failed],
                "sources_failed": failed,
            },
            body=body,
        )
        logger.info("Digest written for %s", topic["name"])

    if not IN_ACTIONS:
        sync_vault(vault["local_path"], f"KnowledgeTracker: daily digest {today}")


def run_weekly(cfg: dict, topic_filter: str | None, embedder: SentenceTransformer):
    today = date.today()
    week_start = (today - timedelta(days=7)).isoformat()
    week_end = (today - timedelta(days=1)).isoformat()
    vault = cfg["obsidian_vault"]

    for topic in cfg["topics"]:
        if topic_filter and topic["name"] != topic_filter:
            continue
        logger.info("Running weekly deep dive for: %s", topic["name"])

        digest_dir = os.path.join(vault["local_path"], vault["digests_folder"], topic["slug"])
        articles = parse_week_digests(digest_dir, week_start, week_end,
                                      topic.get("flag_tag", "#deepdive"))
        if not articles:
            logger.info("No flagged articles found for %s — skipping.", topic["name"])
            continue

        prefs = load_preferences(vault["local_path"], vault["preferences_file"], topic["slug"])
        cap = cfg.get("max_articles_deepdive", 15)
        skipped_urls = [a.url for a in articles[cap:]]
        articles = articles[:cap]

        from knowledge_tracker.sources.web_scraper import fetch_url
        from knowledge_tracker.sources.web_search import fetch as search_fetch

        provider = cfg.get("web_search_provider", "tavily")
        n_queries = cfg.get("web_search_queries_per_article", 2)

        phase1_outputs = []
        for article in articles:
            full_content = fetch_url(article.url)
            search_results = []
            for q in [f"{article.title} related work", f"{article.title} counterarguments"][:n_queries]:
                results = search_fetch(q, provider)
                search_results.extend(r.description for r in results[:3])
            output = deepdive_gen.analyse_article(article, full_content, search_results, cfg["claude_model"])
            phase1_outputs.append(output)

        synthesis = deepdive_gen.synthesise(phase1_outputs, articles, topic.get("keywords", []),
                                             prefs, cfg["claude_model"])
        body = deepdive_gen.format_deepdive_body(articles, phase1_outputs, synthesis, skipped_urls)

        write_deepdive(
            vault_path=vault["local_path"],
            folder=vault["deepdive_folder"],
            topic_slug=topic["slug"],
            week_start=week_start,
            frontmatter={
                "date": today.isoformat(),
                "topic": topic["name"],
                "week_start": week_start,
                "week_end": week_end,
                "articles_reviewed": len(articles),
                "manual_links": sum(1 for a in articles if a.source == "manual"),
            },
            body=body,
        )

        update_preferences(vault["local_path"], vault["preferences_file"],
                           topic["slug"], phase1_outputs, articles)
        logger.info("Deep dive written for %s", topic["name"])

    if not IN_ACTIONS:
        sync_vault(vault["local_path"],
                   f"KnowledgeTracker: weekly deep dive {today.isoformat()}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["daily", "weekly"])
    parser.add_argument("--topic", default=None, help="Run for a single topic by name")
    args = parser.parse_args()

    cfg = load_config("config/topics.yaml", validate_env=True)
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    if args.command == "daily":
        run_daily(cfg, args.topic, embedder)
    elif args.command == "weekly":
        run_weekly(cfg, args.topic, embedder)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI is importable**

```bash
python -c "import run; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add run.py
git commit -m "feat: CLI orchestration in run.py"
```

---

## Task 14: GitHub Actions workflows

**Files:**
- Create: `.github/workflows/daily_digest.yml`
- Create: `.github/workflows/weekly_deepdive.yml`

- [ ] **Step 1: Write `daily_digest.yml`**

```yaml
name: Daily Digest

on:
  schedule:
    - cron: '0 7 * * *'
  workflow_dispatch:

jobs:
  daily-digest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout KnowledgeTracker
        uses: actions/checkout@v4
        with:
          persist-credentials: false

      - name: Checkout Obsidian vault
        uses: actions/checkout@v4
        with:
          repository: ${{ vars.VAULT_REPO }}
          ssh-key: ${{ secrets.VAULT_DEPLOY_KEY }}
          path: vault

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run daily digest
        env:
          VAULT_PATH: ${{ github.workspace }}/vault
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
          REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
          REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
          BLUESKY_HANDLE: ${{ secrets.BLUESKY_HANDLE }}
          BLUESKY_PASSWORD: ${{ secrets.BLUESKY_PASSWORD }}
        run: python run.py daily

      - name: Commit and push vault changes
        run: |
          cd vault
          git config user.name "KnowledgeTracker"
          git config user.email "knowledge-tracker@users.noreply.github.com"
          git pull --rebase origin main
          git add .
          git diff --cached --quiet || git commit -m "KnowledgeTracker: daily digest $(date +%Y-%m-%d)"
          git push origin HEAD
```

- [ ] **Step 2: Write `weekly_deepdive.yml`**

```yaml
name: Weekly Deep Dive

on:
  schedule:
    - cron: '0 8 * * 1'
  workflow_dispatch:

jobs:
  weekly-deepdive:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout KnowledgeTracker
        uses: actions/checkout@v4
        with:
          persist-credentials: false

      - name: Checkout Obsidian vault
        uses: actions/checkout@v4
        with:
          repository: ${{ vars.VAULT_REPO }}
          ssh-key: ${{ secrets.VAULT_DEPLOY_KEY }}
          path: vault

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run weekly deep dive
        env:
          VAULT_PATH: ${{ github.workspace }}/vault
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          TAVILY_API_KEY: ${{ secrets.TAVILY_API_KEY }}
          REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
          REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
          BLUESKY_HANDLE: ${{ secrets.BLUESKY_HANDLE }}
          BLUESKY_PASSWORD: ${{ secrets.BLUESKY_PASSWORD }}
        run: python run.py weekly

      - name: Commit and push vault changes
        run: |
          cd vault
          git config user.name "KnowledgeTracker"
          git config user.email "knowledge-tracker@users.noreply.github.com"
          git pull --rebase origin main
          git add .
          git diff --cached --quiet || git commit -m "KnowledgeTracker: weekly deep dive $(date +%Y-%m-%d)"
          git push origin HEAD
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/
git commit -m "feat: GitHub Actions daily and weekly workflows"
```

---

## Task 15: Final integration test + README

**Files:**
- Create: `tests/test_integration.py`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Write integration smoke test**

```python
# tests/test_integration.py
"""
Smoke test: runs the full daily pipeline against a temp vault using mocked sources and Claude.
Does not call real APIs.
"""
import os, shutil, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from sentence_transformers import SentenceTransformer

from knowledge_tracker.models import Article
from knowledge_tracker.config import load_config

MOCK_ARTICLES = [
    Article(url="https://example.com/rag", title="Understanding RAG",
            description="A deep dive into RAG systems", source="hackernews", score=300),
    Article(url="https://example.com/agents", title="LLM Agents",
            description="How LLM agents work", source="reddit", score=150),
]

def test_daily_pipeline(tmp_path, monkeypatch):
    # Set up temp vault
    vault = tmp_path / "vault"
    (vault / "Digests" / "ai_engineering").mkdir(parents=True)

    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "x")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "x")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    cfg = load_config("config/topics.yaml", validate_env=False)
    cfg["obsidian_vault"]["local_path"] = str(vault)

    import run as run_module
    with patch.object(run_module, "_fetch_all_sources",
                      return_value=(MOCK_ARTICLES, [])), \
         patch("knowledge_tracker.generators.digest.claude_client.chat",
               return_value={"body": "## Top Stories\n\n### [RAG](https://example.com/rag)\nGreat article."}):

        run_module.run_daily(cfg, topic_filter="AI Engineering", embedder=embedder)

    digest_file = vault / "Digests" / "ai_engineering"
    files = list(digest_file.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "AI Engineering" in content
    assert "## Manual Links" in content
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Write `.env.example`**

```bash
ANTHROPIC_API_KEY=your-key-here
TAVILY_API_KEY=your-key-here
REDDIT_CLIENT_ID=your-id-here
REDDIT_CLIENT_SECRET=your-secret-here
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_PASSWORD=your-app-password
# VAULT_PATH=/path/to/vault  # only needed if not using config/topics.yaml local_path
```

- [ ] **Step 4: Write `README.md`**

```markdown
# KnowledgeTracker

Daily topic digests and weekly deep dives, saved to your Obsidian vault.

## Setup

1. **Clone this repo** and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. **Edit `config/topics.yaml`** — set your vault path, topics, and sources.

3. **Set environment variables** (copy from `.env.example`):
   ```
   ANTHROPIC_API_KEY=...
   TAVILY_API_KEY=...
   REDDIT_CLIENT_ID=...
   REDDIT_CLIENT_SECRET=...
   BLUESKY_HANDLE=...
   BLUESKY_PASSWORD=...
   ```

4. **Run locally:**
   ```bash
   python run.py daily
   python run.py weekly
   ```

## GitHub Actions

1. Fork/push this repo to GitHub.
2. Add all env vars as repository secrets.
3. Add `VAULT_REPO` as a repository variable (e.g. `yourname/your-vault`).
4. Add an SSH deploy key with write access to your vault repo; save private key as `VAULT_DEPLOY_KEY` secret.
5. Workflows run automatically: daily at 7am UTC, weekly every Monday at 8am UTC. Trigger manually via `workflow_dispatch`.

## Flagging articles for deep dive

In any daily digest file in your vault, add `#deepdive` below an article heading to flag it. Add URLs to the `## Manual Links` section for your own links.

## Preferences

`preferences.md` in your vault is updated automatically each week. Edit it manually in Obsidian to add negative keywords or boost specific domains.
```

- [ ] **Step 5: Final commit**

```bash
git add tests/test_integration.py .env.example README.md
git commit -m "feat: integration smoke test, .env.example, and README"
```
