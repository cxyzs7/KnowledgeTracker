# Design: Cross-Source Convergence, Engagement Scoring, Digest Quality Evaluator

**Date:** 2026-03-27
**Scope:** Three improvements to the daily pipeline: fix a dedup bug, enrich article scoring with engagement and convergence signals, and add automated digest quality evaluation.

---

## 1. Dedup Fix — `semantic_dedup` merged_sources

**Problem:** `semantic_dedup` in `dedup.py` currently appends `articles[idx].url` into `merged_sources` when clustering. `url_dedup` correctly appends source names (e.g. `"reddit"`). The inconsistency means convergence counting (introduced in section 2) would miscount sources for semantically-deduplicated articles.

**Fix:** In the cluster-representative loop in `semantic_dedup`, change `rep.merged_sources.append(articles[idx].url)` to `rep.merged_sources.append(articles[idx].source)`.

No other code depends on `merged_sources` containing URLs — it is passed to Claude as display context and is not rendered anywhere.

---

## 2. Scorer Changes — `preferences/scorer.py`

### Engagement bonus

Add a per-source reference table and a helper function `_engagement_bonus(article)`:

```python
import math

_ENGAGEMENT_REF = {
    "hackernews":     (500,  10),  # (reference_score, max_bonus)
    "reddit":        (5000,  10),
    "twitter":       (1000,   8),
    "bluesky":        (100,   5),
    "youtube":       (1000,   8),
    # github_trending, feeds, web_search: no engagement signal → omitted → 0
}

def _engagement_bonus(article: Article) -> float:
    ref, cap = _ENGAGEMENT_REF.get(article.source, (0, 0))
    if ref == 0:
        return 0.0
    return min(math.log1p(article.score) / math.log1p(ref), 1.0) * cap
```

Example outputs:
- HN 500 pts → `log1p(500)/log1p(500) × 10 = 10.0`
- HN 50 pts  → `log1p(50)/log1p(500) × 10 ≈ 6.4`
- Reddit 500 upvotes → `log1p(500)/log1p(5000) × 10 ≈ 7.2`
- GitHub Trending (score=0) → `0.0`

### Convergence bonus

Add `_convergence_bonus(article)`:

```python
def _convergence_bonus(article: Article) -> float:
    source_names = {s for s in article.merged_sources if not s.startswith("http")}
    unique = len(source_names | {article.source})
    return min((unique - 1) * 5, 15)
```

- 1 source → +0
- 2 sources → +5
- 3 sources → +10
- 4+ sources → +15 (cap)

### Updated total formula

```
total = clamp(semantic + structural + engagement + convergence, −100, 100)
```

Where:
- `semantic = cosine_sim(topic_vec, article_vec) × 60`  (0–60, unchanged)
- `structural = preferred_domain +15 | preferred_author +15 | ref_domain +10 | neg_kw −25 each` (unchanged)
- `engagement = _engagement_bonus(article)` (0–10)
- `convergence = _convergence_bonus(article)` (0–15)

Combined new headroom: up to **+25** added to the existing range. Engagement and convergence cannot cause a semantically irrelevant article to pass the `total > 0` filter on their own.

---

## 3. New Module — `generators/evaluator.py`

### Public interface

```python
def evaluate(
    client: anthropic.Anthropic,
    *,
    model: str,
    articles: list[Article],
    digest_body: str,
) -> dict:
    ...
```

Returns on success:
```python
{
    "quality_groundedness": int,   # 1–5
    "quality_specificity":  int,   # 1–5
    "quality_coverage":     int,   # 1–5
    "quality_format":       int,   # 1–5
    "quality_rationale":    str,   # one sentence summarising the main gap
}
```

Returns `{}` on any failure (API error, malformed response). Quality scoring is non-fatal.

### Rubric definitions

| Dimension | What is scored |
|-----------|---------------|
| groundedness | Every claim in the digest traces back to a provided article; no fabricated details |
| specificity | Entries name concrete tools, people, numbers — not vague summaries |
| coverage | The most significant articles are represented; no glaring omissions |
| format | Highlights section present, thematic sections used correctly, entries well-formed |

### Implementation

Uses a `evaluate_digest` tool call (structured output, same pattern as `generate_digest`) to force integer scores. Passes the full articles list and digest body in the user message.

The `call_with_retry` wrapper handles retries on 429/5xx. A `try/except` wrapping the entire function body ensures any unhandled error returns `{}`.

### `run.py` integration

In `run_daily`, after `digest_gen.generate()` returns `result`:

```python
from knowledge_tracker.generators import evaluator as evaluator_mod

quality = evaluator_mod.evaluate(
    client, model=model, articles=articles, digest_body=result["body"]
)

write_digest(
    ...
    frontmatter={
        "topic": topic["name"],
        "sources_fetched": result["sources_fetched"],
        "sources_failed": result["sources_failed"],
        "article_count": len(articles),
        **quality,   # merges quality_* keys when non-empty
    },
    body=result["body"],
)
```

No new CLI flags. Runs unconditionally on every daily run.

---

## 4. Testing

### `tests/test_dedup.py`
- New: `semantic_dedup` stores source names (not URLs) in `merged_sources`

### `tests/test_scorer.py`
- `_engagement_bonus` returns correct value for HN 500 pts → 10.0
- `_engagement_bonus` returns 0.0 for `github_trending` and `feeds`
- `_convergence_bonus`: 1 source → 0, 2 sources → 5, 4+ sources → 15 cap

### `tests/test_evaluator.py` (new file)
- Happy path: mock `call_with_retry` returns valid tool-use block → assert all five keys present with correct types
- Failure path: mock `call_with_retry` raises exception → assert `evaluate()` returns `{}`

### `tests/test_integration.py`
- Extend existing daily run test: patch `evaluator.evaluate` returning `{"quality_groundedness": 5, "quality_specificity": 4, "quality_coverage": 5, "quality_format": 4, "quality_rationale": "Good."}` and assert those keys appear in the frontmatter written to the vault.

---

## Files changed

| File | Change |
|------|--------|
| `knowledge_tracker/dedup.py` | Fix `merged_sources` to store source names in `semantic_dedup` |
| `knowledge_tracker/preferences/scorer.py` | Add `_ENGAGEMENT_REF`, `_engagement_bonus`, `_convergence_bonus`; update `score_and_filter` formula |
| `knowledge_tracker/generators/evaluator.py` | New file |
| `run.py` | Import and call `evaluator.evaluate`; merge quality keys into frontmatter |
| `tests/test_dedup.py` | One new test |
| `tests/test_scorer.py` | Three new tests |
| `tests/test_evaluator.py` | New file, two tests |
| `tests/test_integration.py` | Extend daily run test |
