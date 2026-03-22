import logging
import numpy as np
from urllib.parse import urlparse
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)


def score_and_filter(
    articles: list[Article],
    topic_config: dict,
    preferences: dict | None,
    embedder: SentenceTransformer,
    max_results: int,
) -> list[Article]:
    prefs = preferences or {}
    preferred_domains = set(prefs.get("preferred_domains", []))
    preferred_authors = set(prefs.get("preferred_authors", []))
    positive_keywords = prefs.get("positive_keywords", [])
    negative_keywords = prefs.get("negative_keywords", [])
    ref_domains = {
        urlparse(u).netloc.lstrip("www.")
        for u in (topic_config.get("reference_links", []) + prefs.get("reference_links", []))
        if u
    }

    # Build topic vector text
    topic_text = " ".join(topic_config.get("keywords", []) + positive_keywords)
    topic_vec = embedder.encode([topic_text], normalize_embeddings=True)

    # Embed articles (reuse if already set)
    for article in articles:
        if article.embedding is None:
            text = f"{article.title} {article.description}"[:512]
            article.embedding = embedder.encode([text], normalize_embeddings=True)[0].tolist()

    scored = []
    for article in articles:
        article_vec = np.array(article.embedding).reshape(1, -1)
        sim = float(cosine_similarity(topic_vec, article_vec)[0][0])
        semantic_score = sim * 60  # 0–60

        structural = 0.0
        domain = urlparse(article.url).netloc.lstrip("www.")
        if domain in preferred_domains:
            structural += 15
        if article.author and article.author in preferred_authors:
            structural += 15
        if domain in ref_domains:
            structural += 10
        text = f"{article.title} {article.description}".lower()
        for kw in negative_keywords:
            if kw.lower() in text:
                structural -= 25

        total = max(-100.0, min(100.0, semantic_score + structural))
        scored.append((total, article))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for score, a in scored if score > 0][:max_results]
