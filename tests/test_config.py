# tests/test_config.py
from knowledge_tracker.config import load_config

def test_load_config_returns_topics():
    cfg = load_config("config/topics.yaml")
    assert len(cfg["topics"]) >= 1
    assert cfg["topics"][0]["slug"] == "ai_engineering"

def test_load_config_defaults():
    cfg = load_config("config/topics.yaml")
    # flag_tag defaults to #deepdive if not set
    topic = cfg["topics"][0]
    assert topic.get("flag_tag", "#deepdive") == "#deepdive"

def test_load_config_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")

def test_load_config_fails_fast_missing_search_key(monkeypatch):
    """web_search_provider=tavily with no TAVILY_API_KEY env var raises at startup."""
    import os, pytest
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with pytest.raises(EnvironmentError, match="TAVILY_API_KEY"):
        load_config("config/topics.yaml", validate_env=True)
