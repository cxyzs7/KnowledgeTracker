import time
from unittest.mock import patch, MagicMock
from knowledge_tracker.sources.reddit import fetch

MOCK_RESPONSE = {
    "data": {
        "children": [
            {"data": {
                "title": "RAG pipelines",
                "permalink": "/r/MachineLearning/comments/abc/rag_pipelines/",
                "score": 400,
                "author": "bob",
                "selftext": "",
                "created_utc": time.time(),  # now — passes 24h cutoff
            }}
        ]
    }
}


@patch("knowledge_tracker.sources.reddit.requests.get")
def test_fetch_returns_articles(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_RESPONSE
    mock_get.return_value = mock_resp

    articles = fetch(subreddits=["MachineLearning"], limit=10)
    assert len(articles) == 1
    assert articles[0].title == "RAG pipelines"
    assert articles[0].source == "reddit"
    assert articles[0].score == 400
    assert "reddit.com" in articles[0].url


@patch("knowledge_tracker.sources.reddit.requests.get")
def test_fetch_returns_empty_on_failure(mock_get):
    mock_get.side_effect = Exception("connection error")
    articles = fetch(subreddits=["MachineLearning"])
    assert articles == []
