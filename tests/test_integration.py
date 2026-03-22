"""Smoke tests for run_daily and run_weekly with all external calls mocked."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Import the run module — it's at repo root
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import run as run_module

from knowledge_tracker.models import Article

SAMPLE_ARTICLES = [
    Article(url="https://example.com/rag", title="RAG is Great", description="A good article.", source="hackernews", score=300),
    Article(url="https://example.com/agents", title="LLM Agents Guide", description="Agents overview.", source="reddit", score=150),
]

MOCK_DIGEST_RESULT = {
    "body": "## Top Stories\n\n### [RAG is Great](https://example.com/rag)\nSummary.\n\n#deepdive\n\n---",
    "sources_fetched": ["hackernews"],
    "sources_failed": [],
}

MOCK_CLAUDE_RESPONSE = MagicMock()
MOCK_CLAUDE_RESPONSE.content = [
    MagicMock(type="tool_use", input={
        "digest_body": MOCK_DIGEST_RESULT["body"],
        "sources_failed": [],
    })
]


@pytest.fixture
def vault(tmp_path):
    """Create a minimal fake vault directory structure."""
    vault_dir = tmp_path / "vault"
    (vault_dir / "Digests" / "ai_engineering").mkdir(parents=True)
    (vault_dir / "DeepDives" / "ai_engineering").mkdir(parents=True)
    return str(vault_dir)


@pytest.fixture
def cfg(vault):
    return {
        "obsidian_vault": {
            "local_path": vault,
            "digests_folder": "Digests",
            "deepdive_folder": "DeepDives",
            "preferences_file": "preferences.md",
        },
        "claude_model": "claude-sonnet-4-6",
        "web_search_provider": "tavily",
        "max_articles_per_digest": 5,
        "max_articles_deepdive": 5,
        "dedup_similarity_threshold": 0.85,
        "topics": [{
            "name": "AI Engineering",
            "slug": "ai_engineering",
            "keywords": ["LLM", "RAG"],
            "reference_links": [],
            "flag_tag": "#deepdive",
            "sources": {"hackernews": True},
        }],
    }


def test_run_daily_creates_digest(cfg, vault):
    """run_daily should produce a digest markdown file in the vault."""
    mock_embeddings = np.array([[0.1] * 384] * len(SAMPLE_ARTICLES))

    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = mock_embeddings

    with (
        patch.object(run_module, "_fetch_all_sources", return_value=(SAMPLE_ARTICLES, ["hackernews"], [])),
        patch("knowledge_tracker.generators.digest.call_with_retry", return_value=MOCK_CLAUDE_RESPONSE),
        patch("knowledge_tracker.dedup._get_model", return_value=mock_embedder),
        patch("knowledge_tracker.preferences.scorer.SentenceTransformer", return_value=mock_embedder),
        patch("sentence_transformers.SentenceTransformer", return_value=mock_embedder),
        patch("anthropic.Anthropic"),
        patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
    ):
        run_module.run_daily(cfg)

    today = __import__("datetime").date.today().isoformat()
    digest_path = Path(vault) / "Digests" / "ai_engineering" / f"{today}.md"
    assert digest_path.exists(), f"Expected digest at {digest_path}"
    content = digest_path.read_text()
    assert "## Top Stories" in content
    assert "## Manual Links" in content


def test_run_weekly_creates_deepdive(cfg, vault):
    """run_weekly should produce a deep dive markdown file when flagged articles exist."""
    import datetime, shutil
    # Seed a digest file in the vault with a flagged article
    week_start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    digest_dir = Path(vault) / "Digests" / "ai_engineering"
    seed_date = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
    (digest_dir / f"{seed_date}.md").write_text(
        f"---\ndate: {seed_date}\n---\n\n"
        "## Top Stories\n\n"
        "### [RAG is Great](https://example.com/rag)\nSummary.\n\n#deepdive\n\n---\n\n"
        "## Manual Links\n-\n"
    )

    mock_phase1 = MagicMock()
    mock_phase1.content = [MagicMock(type="tool_use", input={
        "summary": "RAG is useful.", "key_insights": ["insight1"],
        "research_expansion": "More research needed.", "keywords": ["RAG"],
    })]
    mock_synthesis = MagicMock()
    mock_synthesis.content = [MagicMock(type="text", text="Weekly synthesis here.")]

    call_responses = [mock_phase1, mock_synthesis]
    call_iter = iter(call_responses)

    with (
        patch("knowledge_tracker.generators.deepdive.call_with_retry", side_effect=lambda *a, **kw: next(call_iter)),
        patch("knowledge_tracker.sources.web_scraper.fetch_url", return_value="article content"),
        patch("anthropic.Anthropic"),
        patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
    ):
        run_module.run_weekly(cfg)

    deepdive_path = Path(vault) / "DeepDives" / "ai_engineering" / f"{week_start}-week.md"
    assert deepdive_path.exists(), f"Expected deep dive at {deepdive_path}"
    content = deepdive_path.read_text()
    assert "RAG is Great" in content
