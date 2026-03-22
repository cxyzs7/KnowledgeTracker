# tests/test_store.py
import os, tempfile, shutil
from knowledge_tracker.models import Article
from knowledge_tracker.preferences.store import update_preferences, load_preferences

def test_load_preferences_parses_frontmatter(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    shutil.copy("tests/fixtures/sample_preferences.md", prefs_file)
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert "eugeneyan.com" in prefs["preferred_domains"]
    assert "RAG" in prefs["positive_keywords"]

def test_load_preferences_returns_none_when_missing(tmp_path):
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert prefs is None

def test_update_preferences_merges_new_domains(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    shutil.copy("tests/fixtures/sample_preferences.md", prefs_file)
    articles = [Article(url="https://newdomain.com/article", title="T", description="D", source="hn")]
    phase1 = [{"keywords": ["agents", "RAG"]}]
    update_preferences(str(tmp_path), "preferences.md", "ai_engineering", phase1, articles)
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert "newdomain.com" in prefs["preferred_domains"]

def test_update_preferences_deduplicates(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    shutil.copy("tests/fixtures/sample_preferences.md", prefs_file)
    articles = [Article(url="https://eugeneyan.com/post", title="T", description="D", source="hn")]
    phase1 = [{"keywords": ["RAG"]}]
    update_preferences(str(tmp_path), "preferences.md", "ai_engineering", phase1, articles)
    prefs = load_preferences(str(tmp_path), "preferences.md", "ai_engineering")
    assert prefs["preferred_domains"].count("eugeneyan.com") == 1

def test_update_preferences_nonfatal_on_bad_yaml(tmp_path):
    prefs_file = tmp_path / "preferences.md"
    prefs_file.write_text("---\nbad: [yaml: nonsense\n---\nbody\n")
    # Should not raise
    update_preferences(str(tmp_path), "preferences.md", "ai_engineering", [], [])
