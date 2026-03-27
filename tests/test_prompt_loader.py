# tests/test_prompt_loader.py
import pytest
from pathlib import Path
from knowledge_tracker.prompt_loader import load_prompt, load_source_prompt


def test_load_prompt_returns_file_content(tmp_path):
    (tmp_path / "digest.md").write_text("# System\nYou are a curator.")
    result = load_prompt("digest", prompts_dir=tmp_path)
    assert result == "# System\nYou are a curator."


def test_load_prompt_strips_whitespace(tmp_path):
    (tmp_path / "digest.md").write_text("  content  \n\n")
    assert load_prompt("digest", prompts_dir=tmp_path) == "content"


def test_load_prompt_raises_on_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        load_prompt("nonexistent", prompts_dir=tmp_path)


def test_load_source_prompt_returns_content(tmp_path):
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    (sources_dir / "hackernews.md").write_text("HN instructions")
    result = load_source_prompt("hackernews", prompts_dir=tmp_path)
    assert result == "HN instructions"


def test_load_source_prompt_returns_none_for_unknown_source(tmp_path):
    (tmp_path / "sources").mkdir()
    result = load_source_prompt("unknown_source", prompts_dir=tmp_path)
    assert result is None


def test_load_source_prompt_strips_whitespace(tmp_path):
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    (sources_dir / "reddit.md").write_text("  reddit rules  \n\n")
    result = load_source_prompt("reddit", prompts_dir=tmp_path)
    assert result == "reddit rules"


def test_load_source_prompt_raises_when_sources_dir_missing(tmp_path):
    # sources/ subdirectory does not exist at all
    with pytest.raises(FileNotFoundError, match="sources"):
        load_source_prompt("hackernews", prompts_dir=tmp_path)
