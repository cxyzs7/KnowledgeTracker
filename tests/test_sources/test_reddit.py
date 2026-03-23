import respx
import httpx
from knowledge_tracker.sources.reddit import fetch

MOCK_RESPONSE = {
    "data": {
        "children": [
            {"data": {
                "title": "RAG pipelines",
                "url": "https://example.com/rag",
                "score": 400,
                "author": "bob",
                "selftext": "",
            }}
        ]
    }
}


@respx.mock
def test_fetch_returns_articles():
    respx.get("https://www.reddit.com/r/MachineLearning/hot.json").mock(
        return_value=httpx.Response(200, json=MOCK_RESPONSE)
    )
    articles = fetch(subreddits=["MachineLearning"], limit=10)
    assert len(articles) == 1
    assert articles[0].title == "RAG pipelines"
    assert articles[0].source == "reddit"
    assert articles[0].score == 400


@respx.mock
def test_fetch_returns_empty_on_failure():
    respx.get("https://www.reddit.com/r/MachineLearning/hot.json").mock(
        return_value=httpx.Response(429)
    )
    articles = fetch(subreddits=["MachineLearning"])
    assert articles == []
