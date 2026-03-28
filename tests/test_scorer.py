# tests/test_scorer.py
import pytest
from unittest.mock import MagicMock
from knowledge_tracker.models import Article
from knowledge_tracker.preferences.scorer import score_and_filter, _engagement_bonus, _convergence_bonus

def make_article(url, title, desc="", author=None, score=0):
    return Article(url=url, title=title, description=desc, source="hn",
                   author=author, score=score)

def make_sourced_article(source, score, merged_sources=None):
    return Article(
        url=f"https://{source}.com/post",
        title="Test Article",
        description="",
        source=source,
        score=score,
        merged_sources=merged_sources or [],
    )

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
    # Pre-set orthogonal embeddings so semantic_score=0; negative keyword (-25) then drops total <0
    import numpy as np
    for a in articles:
        a.embedding = [0.0, 1.0]
    prefs = {"preferred_domains": [], "preferred_authors": [],
             "positive_keywords": ["RAG"], "negative_keywords": ["crypto"],
             "reference_links": []}
    topic = {"keywords": ["RAG"], "reference_links": []}
    embedder = make_embedder()  # returns [1.0, 0.0] for topic vector → cos_sim with [0,1] = 0
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

def test_engagement_bonus_hn_at_reference_score():
    a = make_sourced_article("hackernews", score=500)
    assert _engagement_bonus(a) == pytest.approx(10.0)

def test_engagement_bonus_zero_for_no_signal_sources():
    for source in ("github_trending", "feeds", "web_search"):
        a = make_sourced_article(source, score=999)
        assert _engagement_bonus(a) == 0.0, f"Expected 0 for source={source}"

def test_engagement_bonus_zero_for_negative_score():
    a = make_sourced_article("reddit", score=-5)
    assert _engagement_bonus(a) == 0.0

def test_convergence_bonus_values():
    # 1 source → 0
    a1 = make_sourced_article("hackernews", score=100, merged_sources=[])
    assert _convergence_bonus(a1) == 0

    # 2 sources → 5
    a2 = make_sourced_article("hackernews", score=100, merged_sources=["reddit"])
    assert _convergence_bonus(a2) == 5

    # 3 sources → 10
    a3 = make_sourced_article("hackernews", score=100, merged_sources=["reddit", "bluesky"])
    assert _convergence_bonus(a3) == 10

    # 4+ sources → capped at 15
    a4 = make_sourced_article("hackernews", score=100, merged_sources=["reddit", "bluesky", "youtube"])
    assert _convergence_bonus(a4) == 15
