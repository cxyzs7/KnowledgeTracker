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
