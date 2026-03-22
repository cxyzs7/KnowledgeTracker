# tests/test_writer.py
import os
from knowledge_tracker.obsidian.writer import write_digest, write_deepdive

def test_write_digest_creates_file(tmp_path):
    vault = tmp_path / "vault"
    (vault / "Digests" / "ai_engineering").mkdir(parents=True)
    write_digest(
        vault_path=str(vault),
        folder="Digests",
        topic_slug="ai_engineering",
        date="2026-03-21",
        frontmatter={"topic": "AI Engineering", "sources_fetched": ["hackernews"], "sources_failed": []},
        body="## Top Stories\n\n### [Article](https://example.com)\nSummary.",
    )
    path = vault / "Digests" / "ai_engineering" / "2026-03-21.md"
    assert path.exists()
    content = path.read_text()
    assert "AI Engineering" in content
    assert "## Manual Links" in content

def test_write_deepdive_creates_file(tmp_path):
    vault = tmp_path / "vault"
    (vault / "DeepDives" / "ai_engineering").mkdir(parents=True)
    write_deepdive(
        vault_path=str(vault),
        folder="DeepDives",
        topic_slug="ai_engineering",
        week_start="2026-03-16",
        frontmatter={"topic": "AI Engineering", "articles_reviewed": 3},
        body="## Article Deep Dives\n...\n## Synthesis\n...",
    )
    path = vault / "DeepDives" / "ai_engineering" / "2026-03-16-week.md"
    assert path.exists()
