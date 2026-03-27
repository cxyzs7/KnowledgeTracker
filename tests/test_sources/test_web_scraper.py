# tests/test_sources/test_web_scraper.py
import respx, httpx
from unittest.mock import patch, MagicMock
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


def test_fetch_feeds_parses_atom():
    mock_entry = MagicMock()
    mock_entry.get = lambda key, default="": {
        "link": "https://example.com/test",
        "title": "Test Article",
        "summary": "A summary",
        "author": "Alice",
    }.get(key, default)

    mock_feed = MagicMock()
    mock_feed.entries = [mock_entry]

    with patch("feedparser.parse", return_value=mock_feed):
        articles = fetch_feeds(["https://example.com/feed"])

    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].source == "feeds"


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
