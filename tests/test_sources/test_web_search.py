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
