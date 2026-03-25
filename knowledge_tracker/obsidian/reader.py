import logging
import re
from pathlib import Path
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
MD_LINK_RE = re.compile(r'\[([^\]]*)\]\((https?://[^\)]+)\)')
BARE_URL_RE = re.compile(r'https?://\S+')


def parse_digest_file(filepath: str, flag_tag: str = "#deepdive") -> tuple[list[Article], list[Article]]:
    flagged, manual = [], []
    tag_re = re.compile(r'(?<!\S)' + re.escape(flag_tag) + r'(?!\S)')
    file_date = Path(filepath).stem  # "2026-03-19"

    try:
        with open(filepath) as f:
            content = f.read()
    except Exception as e:
        logger.warning("Failed to read digest %s: %s", filepath, e)
        return [], []

    # ── Flagged articles ──────────────────────────────────────
    # Split into sections at ### headings or --- separators
    section_re = re.compile(r'(?=^#{2,3} |\n---\n)', re.MULTILINE)
    sections = section_re.split(content)

    for section in sections:
        if not section.startswith("###"):
            continue
        if not tag_re.search(section):
            continue
        heading_line = section.split("\n")[0]
        m = MD_LINK_RE.search(heading_line)
        if m:
            flagged.append(Article(
                url=m.group(2), title=m.group(1),
                description="", source="digest", flagged_date=file_date,
            ))

    # ── Manual links ──────────────────────────────────────────
    manual_match = re.search(r'## Manual Links\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if manual_match:
        for line in manual_match.group(1).split("\n"):
            line = line.strip().lstrip("- ").strip()
            if not line or line.startswith("<!--"):
                continue
            m = MD_LINK_RE.search(line)
            if m:
                manual.append(Article(url=m.group(2), title=m.group(1),
                                      description="", source="manual", flagged_date=file_date))
            else:
                url_m = BARE_URL_RE.search(line)
                if url_m:
                    manual.append(Article(url=url_m.group(), title="",
                                          description="", source="manual", flagged_date=file_date))

    return flagged, manual


def parse_seen_urls(digest_dir: str, lookback_days: int = 7) -> set[str]:
    """Return all URLs found in digest files written within the last lookback_days."""
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=lookback_days)
    seen: set[str] = set()
    try:
        files = list(Path(digest_dir).glob("*.md"))
    except Exception:
        return seen
    for f in files:
        try:
            file_date = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if file_date <= cutoff:
            continue
        try:
            content = f.read_text()
        except Exception:
            continue
        for _, url in MD_LINK_RE.findall(content):
            seen.add(url)
    return seen


def parse_week_digests(
    digest_dir: str,
    week_start: str,
    week_end: str,
    flag_tag: str = "#deepdive",
) -> list[Article]:
    from datetime import date as date_cls
    start = date_cls.fromisoformat(week_start)
    end = date_cls.fromisoformat(week_end)

    all_articles: dict[str, Article] = {}
    for f in sorted(Path(digest_dir).glob("*.md")):
        try:
            file_date = date_cls.fromisoformat(f.stem)
        except ValueError:
            continue
        if not (start <= file_date <= end):
            continue
        flagged, manual = parse_digest_file(str(f), flag_tag)
        for article in flagged + manual:
            if article.url not in all_articles:
                all_articles[article.url] = article

    return list(all_articles.values())
