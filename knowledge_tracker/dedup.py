import logging
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def url_dedup(articles: list[Article]) -> list[Article]:
    """Deduplicate by exact URL. Keep highest-score; record merged sources."""
    seen: dict[str, Article] = {}
    for article in articles:
        url = article.url
        if url not in seen:
            seen[url] = article
        else:
            existing = seen[url]
            if article.score > existing.score:
                article.merged_sources = existing.merged_sources + [existing.source]
                seen[url] = article
            else:
                existing.merged_sources.append(article.source)
    return list(seen.values())


def semantic_dedup(articles: list[Article], threshold: float = 0.85) -> list[Article]:
    """Cluster semantically similar articles; keep highest-score representative."""
    if len(articles) <= 1:
        return articles

    model = _get_model()
    texts = [f"{a.title} {a.description}"[:512] for a in articles]
    embeddings = model.encode(texts, normalize_embeddings=True)

    # Store embeddings on articles for reuse in scorer
    for article, emb in zip(articles, embeddings):
        article.embedding = emb.tolist()

    sim_matrix = cosine_similarity(embeddings)
    n = len(articles)
    visited = [False] * n
    clusters: list[list[int]] = []

    for i in range(n):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if not visited[j] and sim_matrix[i][j] >= threshold:
                cluster.append(j)
                visited[j] = True
        clusters.append(cluster)

    result = []
    for cluster in clusters:
        best_idx = max(cluster, key=lambda i: articles[i].score)
        rep = articles[best_idx]
        for idx in cluster:
            if idx != best_idx:
                rep.merged_sources.append(articles[idx].source)
        result.append(rep)

    return result
