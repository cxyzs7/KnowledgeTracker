import respx
import httpx
import pytest
from knowledge_tracker.sources.youtube import fetch


MOCK_VIDEOS_RESPONSE = {
    "data": [
        {
            "id": "abc123xyz",
            "title": "The Future of AI Agents",
            "publishedAt": "2026-03-25T14:00:00Z",
            "description": "Episode summary here.",
        }
    ]
}

MOCK_TRANSCRIPT_RESPONSE = {
    "content": "Welcome to Latent Space. Today we discuss agent architectures..."
}


@respx.mock
def test_fetch_returns_articles_when_api_key_set(monkeypatch):
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    respx.get("https://api.supadata.ai/v1/youtube/channel/videos").mock(
        return_value=httpx.Response(200, json=MOCK_VIDEOS_RESPONSE)
    )
    respx.get("https://api.supadata.ai/v1/youtube/transcript").mock(
        return_value=httpx.Response(200, json=MOCK_TRANSCRIPT_RESPONSE)
    )
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert len(articles) == 1
    assert articles[0].title == "The Future of AI Agents"
    assert articles[0].source == "youtube"
    assert articles[0].author == "Latent Space"
    assert "agent architectures" in articles[0].description
    assert articles[0].url == "https://www.youtube.com/watch?v=abc123xyz"


def test_fetch_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("SUPADATA_API_KEY", raising=False)
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert articles == []


@respx.mock
def test_fetch_returns_empty_on_api_error(monkeypatch):
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    respx.get("https://api.supadata.ai/v1/youtube/channel/videos").mock(
        return_value=httpx.Response(500)
    )
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert articles == []


@respx.mock
def test_fetch_falls_back_to_description_on_transcript_failure(monkeypatch):
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    respx.get("https://api.supadata.ai/v1/youtube/channel/videos").mock(
        return_value=httpx.Response(200, json=MOCK_VIDEOS_RESPONSE)
    )
    respx.get("https://api.supadata.ai/v1/youtube/transcript").mock(
        return_value=httpx.Response(404)
    )
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert len(articles) == 1
    assert articles[0].description == "Episode summary here."
