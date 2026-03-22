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
