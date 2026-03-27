import respx
import httpx
import pytest
from knowledge_tracker.sources.twitter import fetch

MOCK_TWEETS_RESPONSE = {
    "data": [
        {
            "id": "1234567890",
            "text": "Exciting progress on inference-time compute scaling today. Here's what matters...",
            "created_at": "2026-03-26T10:00:00Z",
        }
    ]
}


@respx.mock
def test_fetch_returns_articles_when_token_set(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    respx.get("https://api.twitter.com/2/users/33836629/tweets").mock(
        return_value=httpx.Response(200, json=MOCK_TWEETS_RESPONSE)
    )
    accounts = [{"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"}]
    articles = fetch(accounts)
    assert len(articles) == 1
    assert articles[0].source == "twitter"
    assert articles[0].author == "Andrej Karpathy"
    assert articles[0].url == "https://twitter.com/karpathy/status/1234567890"


def test_fetch_returns_empty_without_token(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    accounts = [{"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"}]
    assert fetch(accounts) == []


@respx.mock
def test_fetch_returns_empty_on_api_error(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    respx.get("https://api.twitter.com/2/users/33836629/tweets").mock(
        return_value=httpx.Response(429)
    )
    accounts = [{"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"}]
    assert fetch(accounts) == []


@respx.mock
def test_fetch_handles_multiple_accounts(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    respx.get("https://api.twitter.com/2/users/33836629/tweets").mock(
        return_value=httpx.Response(200, json=MOCK_TWEETS_RESPONSE)
    )
    respx.get("https://api.twitter.com/2/users/12631042/tweets").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    accounts = [
        {"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"},
        {"id": "12631042", "handle": "sama", "name": "Sam Altman"},
    ]
    articles = fetch(accounts)
    assert len(articles) == 1  # sama had no tweets
