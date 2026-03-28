# tests/test_dedup.py
from knowledge_tracker.models import Article
from knowledge_tracker.dedup import url_dedup, semantic_dedup

def make_article(url, title, desc="", score=0, source="hn"):
    return Article(url=url, title=title, description=desc, source=source, score=score)

def test_url_dedup_removes_duplicates():
    articles = [
        make_article("https://example.com/a", "Article A", score=100, source="hackernews"),
        make_article("https://example.com/a", "Article A", score=50, source="reddit"),
        make_article("https://example.com/b", "Article B"),
    ]
    result = url_dedup(articles)
    assert len(result) == 2
    # higher-score source kept
    a = next(r for r in result if r.url == "https://example.com/a")
    assert a.score == 100
    assert "reddit" in a.merged_sources

def test_url_dedup_preserves_unique():
    articles = [make_article("https://a.com", "A"), make_article("https://b.com", "B")]
    assert len(url_dedup(articles)) == 2

def test_semantic_dedup_clusters_similar():
    # Two topically related titles should be clustered.
    # Actual cosine similarity for this RAG pair via all-MiniLM-L6-v2 is ~0.43,
    # so threshold is set to 0.40 (RAG vs pasta similarity is ~0.04-0.10).
    articles = [
        make_article("https://a.com", "Introduction to RAG systems for LLMs", score=100),
        make_article("https://b.com", "Getting started with RAG for large language models", score=50),
        make_article("https://c.com", "How to cook pasta at home", score=200),
    ]
    result = semantic_dedup(articles, threshold=0.40)
    # pasta article must survive; RAG pair should be 1
    urls = {r.url for r in result}
    assert "https://c.com" in urls
    assert len(result) == 2  # RAG pair clustered into one

def test_semantic_dedup_keeps_highest_score_representative():
    articles = [
        make_article("https://a.com", "RAG retrieval augmented generation tutorial", score=50),
        make_article("https://b.com", "RAG retrieval augmented generation guide", score=200),
    ]
    result = semantic_dedup(articles, threshold=0.80)
    assert len(result) == 1
    assert result[0].score == 200
    assert result[0].url == "https://b.com"
    assert "hn" in result[0].merged_sources

def test_semantic_dedup_stores_source_name_not_url_in_merged_sources():
    articles = [
        make_article("https://a.com", "RAG retrieval augmented generation tutorial", score=50, source="hackernews"),
        make_article("https://b.com", "RAG retrieval augmented generation guide", score=200, source="reddit"),
    ]
    result = semantic_dedup(articles, threshold=0.80)
    assert len(result) == 1
    rep = result[0]
    assert "hackernews" in rep.merged_sources
    assert not any(s.startswith("http") for s in rep.merged_sources)
