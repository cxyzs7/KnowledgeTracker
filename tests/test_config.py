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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    with pytest.raises(EnvironmentError, match="TAVILY_API_KEY"):
        load_config("config/topics.yaml", validate_env=True)


def test_load_builders_config_returns_accounts_and_channels(tmp_path):
    yaml_content = """
twitter:
  accounts:
    - handle: karpathy
      id: "33836629"
      name: Andrej Karpathy
youtube:
  channels:
    - id: UCXZCJLdBC09xxGZ6gcdrc6A
      name: Latent Space
blogs:
  feeds:
    - url: https://eugeneyan.com/rss.xml
      name: Eugene Yan
"""
    p = tmp_path / "builders.yaml"
    p.write_text(yaml_content)
    from knowledge_tracker.config import load_builders_config
    cfg = load_builders_config(str(p))
    assert cfg["twitter"]["accounts"][0]["handle"] == "karpathy"
    assert cfg["youtube"]["channels"][0]["name"] == "Latent Space"
    assert cfg["blogs"]["feeds"][0]["url"] == "https://eugeneyan.com/rss.xml"


def test_load_builders_config_returns_empty_dict_when_missing(tmp_path):
    from knowledge_tracker.config import load_builders_config
    cfg = load_builders_config(str(tmp_path / "nonexistent.yaml"))
    assert cfg == {}
