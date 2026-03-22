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
