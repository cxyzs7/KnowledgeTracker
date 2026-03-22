# tests/test_reader.py
import shutil
from pathlib import Path
from knowledge_tracker.obsidian.reader import parse_digest_file, parse_week_digests

def test_parse_digest_file_finds_flagged(tmp_path):
    shutil.copy("tests/fixtures/sample_digest.md", tmp_path / "2026-03-19.md")
    flagged, manual = parse_digest_file(str(tmp_path / "2026-03-19.md"), flag_tag="#deepdive")
    assert len(flagged) == 1
    assert flagged[0].url == "https://example.com/rag"
    assert flagged[0].flagged_date == "2026-03-19"

def test_parse_digest_file_finds_manual_links(tmp_path):
    shutil.copy("tests/fixtures/sample_digest.md", tmp_path / "2026-03-19.md")
    flagged, manual = parse_digest_file(str(tmp_path / "2026-03-19.md"), flag_tag="#deepdive")
    assert len(manual) == 2
    assert any("manual.com/link1" in m.url for m in manual)
    assert any("manual.com/link2" in m.url for m in manual)

def test_parse_digest_file_ignores_empty_manual_lines(tmp_path):
    shutil.copy("tests/fixtures/sample_digest.md", tmp_path / "2026-03-19.md")
    _, manual = parse_digest_file(str(tmp_path / "2026-03-19.md"), flag_tag="#deepdive")
    # bare "-" lines must be excluded
    assert all(m.url for m in manual)

def test_parse_week_digests_deduplicates_by_url(tmp_path):
    digest_dir = tmp_path / "digests"
    digest_dir.mkdir()
    # Same file copied to two different days
    shutil.copy("tests/fixtures/sample_digest.md", digest_dir / "2026-03-18.md")
    shutil.copy("tests/fixtures/sample_digest.md", digest_dir / "2026-03-19.md")
    articles = parse_week_digests(str(digest_dir), "2026-03-16", "2026-03-22", "#deepdive")
    urls = [a.url for a in articles]
    assert urls.count("https://example.com/rag") == 1
