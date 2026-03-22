import logging
import os
import re
from urllib.parse import urlparse
import yaml
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)


def load_preferences(vault_path: str, prefs_file: str, topic_slug: str) -> dict | None:
    path = os.path.join(vault_path, prefs_file)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            content = f.read()
        m = FRONTMATTER_RE.match(content)
        if not m:
            return None
        data = yaml.safe_load(m.group(1))
        return data.get("topics", {}).get(topic_slug)
    except Exception as e:
        logger.warning("Failed to load preferences: %s", e)
        return None


def update_preferences(
    vault_path: str,
    prefs_file: str,
    topic_slug: str,
    phase1_outputs: list[dict],
    articles: list[Article],
) -> None:
    path = os.path.join(vault_path, prefs_file)
    try:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
            m = FRONTMATTER_RE.match(content)
            body = content[m.end():] if m else "\n# My Reading Preferences\n\nAuto-updated weekly.\n"
            data = yaml.safe_load(m.group(1)) if m else {}
        else:
            data = {}
            body = "\n# My Reading Preferences\n\nAuto-updated weekly.\n"

        data.setdefault("topics", {})
        data["topics"].setdefault(topic_slug, {
            "preferred_domains": [], "preferred_authors": [],
            "positive_keywords": [], "negative_keywords": [], "reference_links": [],
        })
        topic_prefs = data["topics"][topic_slug]

        # Extract domains
        for article in articles:
            domain = urlparse(article.url).netloc.lstrip("www.")
            if domain and domain not in topic_prefs["preferred_domains"]:
                topic_prefs["preferred_domains"].append(domain)

        # Extract authors
        for article in articles:
            if article.author and article.author not in topic_prefs["preferred_authors"]:
                topic_prefs["preferred_authors"].append(article.author)

        # Extract keywords from Phase 1
        for output in phase1_outputs:
            for kw in output.get("keywords", []):
                if kw and kw not in topic_prefs["positive_keywords"]:
                    topic_prefs["positive_keywords"].append(kw)

        import datetime
        data["updated"] = datetime.date.today().isoformat()
        new_frontmatter = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        with open(path, "w") as f:
            f.write(f"---\n{new_frontmatter}---\n{body}")

    except Exception as e:
        logger.error("Failed to update preferences.md (non-fatal): %s", e)
