# Scoring and Evaluator Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-source convergence and per-source engagement bonuses to the article scorer, fix a bug in semantic dedup, and add an automated digest quality evaluator that runs at the end of each daily pipeline and writes rubric scores to digest frontmatter.

**Architecture:** Four surgical changes — fix one line in `dedup.py`, add two helper functions and update the formula in `scorer.py`, create a new `generators/evaluator.py` module, and wire the evaluator into `run.py`. Each change is independently testable.

**Tech Stack:** Python, `math` (stdlib), `anthropic` SDK, `unittest.mock`, `pytest`

---

## File Map

| File | Change |
|------|--------|
| `knowledge_tracker/dedup.py` | Fix `semantic_dedup` to store source names (not URLs) in `merged_sources` |
| `knowledge_tracker/preferences/scorer.py` | Add `import math`, `_ENGAGEMENT_REF`, `_engagement_bonus`, `_convergence_bonus`; update formula in `score_and_filter` |
| `knowledge_tracker/generators/evaluator.py` | New file — `evaluate()` function |
| `run.py` | Import `evaluator` module; call after `digest_gen.generate()`; merge quality keys into frontmatter |
| `tests/test_dedup.py` | One new test for source-name storage |
| `tests/test_scorer.py` | Three new tests for bonus functions |
| `tests/test_evaluator.py` | New file — happy path + failure path |
| `tests/test_integration.py` | Extend daily run test to assert quality keys in frontmatter |

---

## Task 1: Fix `semantic_dedup` to store source names

**Files:**
- Modify: `knowledge_tracker/dedup.py:70`
- Test: `tests/test_dedup.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dedup.py`:

```python
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
```

Note: `make_article` already accepts `source` as a kwarg. Check the existing signature:
```python
def make_article(url, title, desc="", score=0, source="hn"):
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_dedup.py::test_semantic_dedup_stores_source_name_not_url_in_merged_sources -v
```

Expected: FAIL — `assert "hackernews" in rep.merged_sources` fails because the URL `"https://a.com"` is stored instead.

- [ ] **Step 3: Fix `semantic_dedup`**

In `knowledge_tracker/dedup.py`, find this block (lines 64–71):

```python
    result = []
    for cluster in clusters:
        best_idx = max(cluster, key=lambda i: articles[i].score)
        rep = articles[best_idx]
        for idx in cluster:
            if idx != best_idx:
                rep.merged_sources.append(articles[idx].url)
        result.append(rep)
```

Change `articles[idx].url` to `articles[idx].source`:

```python
    result = []
    for cluster in clusters:
        best_idx = max(cluster, key=lambda i: articles[i].score)
        rep = articles[best_idx]
        for idx in cluster:
            if idx != best_idx:
                rep.merged_sources.append(articles[idx].source)
        result.append(rep)
```

- [ ] **Step 4: Run all dedup tests**

```bash
uv run pytest tests/test_dedup.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_tracker/dedup.py tests/test_dedup.py
git commit -m "fix: semantic_dedup stores source names in merged_sources, not URLs"
```

---

## Task 2: Add engagement and convergence bonuses to scorer

**Files:**
- Modify: `knowledge_tracker/preferences/scorer.py`
- Test: `tests/test_scorer.py`

- [ ] **Step 1: Write the three failing tests**

Add to `tests/test_scorer.py` (after the existing imports and helpers):

```python
import math
import pytest
from knowledge_tracker.preferences.scorer import _engagement_bonus, _convergence_bonus


def make_sourced_article(source, score, merged_sources=None):
    return Article(
        url=f"https://{source}.com/post",
        title="Test Article",
        description="",
        source=source,
        score=score,
        merged_sources=merged_sources or [],
    )


def test_engagement_bonus_hn_at_reference_score():
    a = make_sourced_article("hackernews", score=500)
    assert _engagement_bonus(a) == pytest.approx(10.0)


def test_engagement_bonus_zero_for_no_signal_sources():
    for source in ("github_trending", "feeds", "web_search"):
        a = make_sourced_article(source, score=999)
        assert _engagement_bonus(a) == 0.0, f"Expected 0 for source={source}"


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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_scorer.py::test_engagement_bonus_hn_at_reference_score tests/test_scorer.py::test_engagement_bonus_zero_for_no_signal_sources tests/test_scorer.py::test_convergence_bonus_values -v
```

Expected: All FAIL — `ImportError: cannot import name '_engagement_bonus'`.

- [ ] **Step 3: Add `import math`, the reference table, and helper functions to `scorer.py`**

Open `knowledge_tracker/preferences/scorer.py`. Add `import math` to the imports block (after the existing imports):

```python
import logging
import math
import numpy as np
from urllib.parse import urlparse
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from knowledge_tracker.models import Article
```

Then add the reference table and helper functions after the `logger` line and before `score_and_filter`:

```python
_ENGAGEMENT_REF: dict[str, tuple[int, float]] = {
    "hackernews": (500, 10),
    "reddit":    (5000, 10),
    "twitter":   (1000,  8),
    "bluesky":    (100,  5),
    "youtube":   (1000,  8),
}


def _engagement_bonus(article: Article) -> float:
    ref, cap = _ENGAGEMENT_REF.get(article.source, (0, 0))
    if ref == 0:
        return 0.0
    return min(math.log1p(article.score) / math.log1p(ref), 1.0) * cap


def _convergence_bonus(article: Article) -> float:
    source_names = {s for s in article.merged_sources if not s.startswith("http")}
    unique = len(source_names | {article.source})
    return min((unique - 1) * 5, 15)
```

- [ ] **Step 4: Update the scoring formula inside `score_and_filter`**

Find this block in `score_and_filter` (currently around line 58):

```python
        total = max(-100.0, min(100.0, semantic_score + structural))
        scored.append((total, article))
```

Replace with:

```python
        engagement = _engagement_bonus(article)
        convergence = _convergence_bonus(article)
        total = max(-100.0, min(100.0, semantic_score + structural + engagement + convergence))
        scored.append((total, article))
```

- [ ] **Step 5: Run all scorer tests**

```bash
uv run pytest tests/test_scorer.py -v
```

Expected: All PASS (including the three new tests and the three existing ones).

- [ ] **Step 6: Commit**

```bash
git add knowledge_tracker/preferences/scorer.py tests/test_scorer.py
git commit -m "feat: add per-source engagement and cross-source convergence bonuses to scorer"
```

---

## Task 3: Create `generators/evaluator.py`

**Files:**
- Create: `knowledge_tracker/generators/evaluator.py`
- Create: `tests/test_evaluator.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evaluator.py`:

```python
from unittest.mock import MagicMock, patch
from knowledge_tracker.generators.evaluator import evaluate
from knowledge_tracker.models import Article

SAMPLE_ARTICLE = Article(
    url="https://example.com/rag",
    title="RAG Overview",
    description="About RAG systems.",
    source="hackernews",
    score=200,
)

MOCK_EVAL_RESPONSE = MagicMock()
MOCK_EVAL_RESPONSE.content = [
    MagicMock(
        type="tool_use",
        input={
            "quality_groundedness": 4,
            "quality_specificity": 3,
            "quality_coverage": 5,
            "quality_format": 4,
            "quality_rationale": "Strong coverage; one vague highlight bullet.",
        },
    )
]


def test_evaluate_returns_scores_on_success():
    with patch("knowledge_tracker.generators.evaluator.call_with_retry", return_value=MOCK_EVAL_RESPONSE):
        result = evaluate(
            MagicMock(),
            model="claude-sonnet-4-6",
            articles=[SAMPLE_ARTICLE],
            digest_body="### Highlights\n- RAG improves retrieval.\n\n#### 🔥 Top Stories\n**RAG Overview** — summary. [hackernews](https://example.com/rag)",
        )
    assert result["quality_groundedness"] == 4
    assert result["quality_specificity"] == 3
    assert result["quality_coverage"] == 5
    assert result["quality_format"] == 4
    assert isinstance(result["quality_rationale"], str)


def test_evaluate_returns_empty_dict_on_api_failure():
    with patch("knowledge_tracker.generators.evaluator.call_with_retry", side_effect=Exception("500 API error")):
        result = evaluate(
            MagicMock(),
            model="claude-sonnet-4-6",
            articles=[SAMPLE_ARTICLE],
            digest_body="### Highlights\n- RAG is useful.",
        )
    assert result == {}
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_evaluator.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'knowledge_tracker.generators.evaluator'`.

- [ ] **Step 3: Create `knowledge_tracker/generators/evaluator.py`**

```python
import logging
import anthropic
from knowledge_tracker.models import Article
from knowledge_tracker.claude_client import call_with_retry

logger = logging.getLogger(__name__)

_EVALUATE_TOOL = {
    "name": "evaluate_digest",
    "description": "Score a generated digest on four quality dimensions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "quality_groundedness": {
                "type": "integer",
                "description": "1-5: every claim in the digest traces back to a provided article",
            },
            "quality_specificity": {
                "type": "integer",
                "description": "1-5: entries name concrete tools, people, or numbers rather than vague summaries",
            },
            "quality_coverage": {
                "type": "integer",
                "description": "1-5: the most significant articles are represented with no glaring omissions",
            },
            "quality_format": {
                "type": "integer",
                "description": "1-5: highlights section present, thematic sections used correctly, entries well-formed",
            },
            "quality_rationale": {
                "type": "string",
                "description": "one sentence summarising the main quality gap or notable strength",
            },
        },
        "required": [
            "quality_groundedness",
            "quality_specificity",
            "quality_coverage",
            "quality_format",
            "quality_rationale",
        ],
    },
}


def evaluate(
    client: anthropic.Anthropic,
    *,
    model: str,
    articles: list[Article],
    digest_body: str,
) -> dict:
    """Evaluate digest quality against source articles. Returns score dict or {} on failure."""
    try:
        articles_text = "\n\n".join(
            f"[{i + 1}] {a.title} — {a.description[:200]}"
            for i, a in enumerate(articles)
        )
        prompt = (
            f"Source articles provided to the digest generator:\n{articles_text}"
            f"\n\nGenerated digest:\n{digest_body}"
            "\n\nScore the digest on each dimension from 1 (poor) to 5 (excellent)."
        )
        response = call_with_retry(
            client,
            model=model,
            max_tokens=512,
            system="You are a precise quality evaluator. Score only what you can observe in the provided text.",
            tools=[_EVALUATE_TOOL],
            messages=[{"role": "user", "content": prompt}],
            tool_choice={"type": "tool", "name": "evaluate_digest"},
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            logger.warning("evaluator: no tool_use block in response")
            return {}
        return tool_use.input
    except Exception as e:
        logger.warning("Digest evaluation failed: %s", e)
        return {}
```

- [ ] **Step 4: Run all evaluator tests**

```bash
uv run pytest tests/test_evaluator.py -v
```

Expected: Both PASS.

- [ ] **Step 5: Commit**

```bash
git add knowledge_tracker/generators/evaluator.py tests/test_evaluator.py
git commit -m "feat: add digest quality evaluator with four-dimension rubric"
```

---

## Task 4: Wire evaluator into `run.py` and integration test

**Files:**
- Modify: `run.py`
- Test: `tests/test_integration.py`

- [ ] **Step 1: Write the failing integration test**

Add a new test to `tests/test_integration.py`. Add it after `test_run_daily_creates_digest`. It needs the same fixtures (`cfg`, `vault`) already defined in that file.

```python
def test_run_daily_writes_quality_scores_to_frontmatter(cfg, vault):
    """Quality scores returned by evaluator.evaluate appear in the digest frontmatter."""
    mock_embeddings = np.array([[0.1] * 384] * len(SAMPLE_ARTICLES))
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = mock_embeddings

    mock_quality = {
        "quality_groundedness": 5,
        "quality_specificity": 4,
        "quality_coverage": 5,
        "quality_format": 4,
        "quality_rationale": "Excellent digest.",
    }

    with (
        patch.object(run_module, "_fetch_all_sources", return_value=(SAMPLE_ARTICLES, ["hackernews"], [])),
        patch("knowledge_tracker.generators.digest.call_with_retry", return_value=MOCK_CLAUDE_RESPONSE),
        patch("knowledge_tracker.generators.evaluator.call_with_retry", return_value=MagicMock(
            content=[MagicMock(type="tool_use", input=mock_quality)]
        )),
        patch("knowledge_tracker.dedup._get_model", return_value=mock_embedder),
        patch("knowledge_tracker.preferences.scorer.SentenceTransformer", return_value=mock_embedder),
        patch("sentence_transformers.SentenceTransformer", return_value=mock_embedder),
        patch("anthropic.Anthropic"),
        patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
    ):
        run_module.run_daily(cfg)

    today = __import__("datetime").date.today().isoformat()
    digest_path = Path(vault) / "Digests" / "ai_engineering" / f"{today}.md"
    content = digest_path.read_text()
    assert "quality_groundedness: 5" in content
    assert "quality_coverage: 5" in content
    assert "quality_rationale: Excellent digest." in content
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_integration.py::test_run_daily_writes_quality_scores_to_frontmatter -v
```

Expected: FAIL — `quality_groundedness` not in digest content because `run.py` doesn't call the evaluator yet.

- [ ] **Step 3: Update `run.py`**

Add the evaluator import near the other generator imports (around line 28–30):

```python
from knowledge_tracker.generators import digest as digest_gen
from knowledge_tracker.generators import deepdive as deepdive_gen
from knowledge_tracker.generators import evaluator as evaluator_mod
```

Then in `run_daily`, find the block after `digest_gen.generate()` returns (around line 184–203):

```python
        # Generate digest via Claude
        result = digest_gen.generate(
            client, model=model, topic=topic,
            articles=articles, prefs=prefs, date=today, sources_fetched=fetched,
        )

        # Write to vault
        write_digest(
            vault_path=vault_path,
            folder=digests_folder,
            topic_slug=slug,
            date=today,
            frontmatter={
                "topic": topic["name"],
                "sources_fetched": result["sources_fetched"],
                "sources_failed": result["sources_failed"],
                "article_count": len(articles),
            },
            body=result["body"],
        )
```

Replace with:

```python
        # Generate digest via Claude
        result = digest_gen.generate(
            client, model=model, topic=topic,
            articles=articles, prefs=prefs, date=today, sources_fetched=fetched,
        )

        # Evaluate digest quality (non-fatal — returns {} on failure)
        quality = evaluator_mod.evaluate(
            client, model=model, articles=articles, digest_body=result["body"]
        )

        # Write to vault
        write_digest(
            vault_path=vault_path,
            folder=digests_folder,
            topic_slug=slug,
            date=today,
            frontmatter={
                "topic": topic["name"],
                "sources_fetched": result["sources_fetched"],
                "sources_failed": result["sources_failed"],
                "article_count": len(articles),
                **quality,
            },
            body=result["body"],
        )
```

- [ ] **Step 4: Run all integration tests**

```bash
uv run pytest tests/test_integration.py -v
```

Expected: All PASS.

- [ ] **Step 5: Run the full test suite**

```bash
uv run pytest
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add run.py tests/test_integration.py
git commit -m "feat: wire digest quality evaluator into daily pipeline; scores written to frontmatter"
```
