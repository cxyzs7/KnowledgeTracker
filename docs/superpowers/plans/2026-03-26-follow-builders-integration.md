# Follow-Builders Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incorporate prompt files, per-source prompt templates, YouTube/podcast source, Twitter/X source, and curated builder config from the follow-builders repo into KnowledgeTracker.

**Architecture:** A new `prompt_loader` module reads markdown files from `prompts/` at runtime, replacing all hardcoded strings in `digest.py` and `deepdive.py`. Two optional source modules (`youtube.py`, `twitter.py`) silently no-op when credentials are absent. A new `config/builders.yaml` holds a globally-applied curated builder list loaded alongside `topics.yaml`.

**Tech Stack:** Python 3.12, httpx (YouTube/Twitter HTTP calls), existing `Article` dataclass, existing `call_with_retry` Claude wrapper, PyYAML, pytest + respx for tests.

---

## File Map

**New files:**
- `knowledge_tracker/prompt_loader.py` — `load_prompt(name)` and `load_source_prompt(source)` functions
- `prompts/digest.md` — main digest system prompt
- `prompts/deepdive_analyse.md` — per-article analysis system prompt
- `prompts/deepdive_synthesise.md` — weekly synthesis system prompt
- `prompts/sources/hackernews.md` — HN-specific instructions
- `prompts/sources/reddit.md`
- `prompts/sources/bluesky.md` — adapted from follow-builders tweet prompt
- `prompts/sources/feeds.md` — adapted from follow-builders blog prompt
- `prompts/sources/github_trending.md`
- `prompts/sources/web_search.md`
- `prompts/sources/youtube.md` — from follow-builders podcast prompt
- `prompts/sources/twitter.md` — from follow-builders tweet prompt
- `config/builders.yaml` — curated builder accounts, YouTube channels, blog feeds
- `knowledge_tracker/sources/youtube.py` — Supadata API, optional
- `knowledge_tracker/sources/twitter.py` — X API v2, optional
- `tests/test_prompt_loader.py`
- `tests/test_generators.py`
- `tests/test_sources/test_youtube.py`
- `tests/test_sources/test_twitter.py`

**Modified files:**
- `knowledge_tracker/generators/digest.py` — use `load_prompt` + append per-source sections
- `knowledge_tracker/generators/deepdive.py` — use `load_prompt` for system prompts
- `knowledge_tracker/config.py` — add `load_builders_config()`
- `knowledge_tracker/sources/__init__.py` — import youtube, twitter
- `run.py` — load builders config, call new sources, pass `builders_cfg` to `_fetch_all_sources`
- `tests/test_integration.py` — update `cfg` fixture, add builder feeds test
- `README.md` — add Optional Sources section

---

## Task 1: Prompt loader module

**Files:**
- Create: `knowledge_tracker/prompt_loader.py`
- Create: `tests/test_prompt_loader.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_prompt_loader.py -v
```
Expected: `ModuleNotFoundError: No module named 'knowledge_tracker.prompt_loader'`

- [ ] **Step 3: Implement the prompt loader**

```python
# knowledge_tracker/prompt_loader.py
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str, prompts_dir: Path | None = None) -> str:
    """Load a top-level prompt file. Raises FileNotFoundError if absent."""
    base = prompts_dir if prompts_dir is not None else PROMPTS_DIR
    path = base / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text().strip()


def load_source_prompt(source: str, prompts_dir: Path | None = None) -> str | None:
    """Load a per-source prompt file. Returns None if no file exists for this source."""
    base = prompts_dir if prompts_dir is not None else PROMPTS_DIR
    path = base / "sources" / f"{source}.md"
    if not path.exists():
        return None
    return path.read_text().strip()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_prompt_loader.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add knowledge_tracker/prompt_loader.py tests/test_prompt_loader.py
git commit -m "feat: add prompt_loader module for file-based prompt loading"
```

---

## Task 2: Create all prompt files

**Files:**
- Create: `prompts/digest.md`
- Create: `prompts/deepdive_analyse.md`
- Create: `prompts/deepdive_synthesise.md`
- Create: `prompts/sources/hackernews.md`
- Create: `prompts/sources/reddit.md`
- Create: `prompts/sources/bluesky.md`
- Create: `prompts/sources/feeds.md`
- Create: `prompts/sources/github_trending.md`
- Create: `prompts/sources/web_search.md`
- Create: `prompts/sources/youtube.md`
- Create: `prompts/sources/twitter.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p prompts/sources
```

- [ ] **Step 2: Create `prompts/digest.md`**

```
You are a senior engineer curating a daily digest for a developer who wants high-signal, actionable content. Your priorities:
- Avoid hype and marketing language. Favour depth and practicality.
- Focus on original opinions, technical insights, product announcements, and industry analysis — not commentary on others' work.
- If the same story appears across multiple sources, merge them into one entry and list all relevant links.
- Omit sections that have nothing worth including today.
- Quality over quantity: a tight digest of 10 great items beats 30 mediocre ones.
```

- [ ] **Step 3: Create `prompts/deepdive_analyse.md`**

```
You are a research assistant performing structured analysis of technical articles. For each article, produce:
- A 2–3 sentence summary of the main argument. State the finding directly — do not write "the article discusses" or "the author argues".
- 3–5 key insights or takeaways.
- A 150–250 word research expansion: what related work exists, open questions, and practical implications.
- 5–10 topic keywords for preference learning.

Be specific and concrete. Use the provided tool.
```

- [ ] **Step 4: Create `prompts/deepdive_synthesise.md`**

```
You are synthesising a week of technical reading into a coherent narrative. Write 400–600 words that:
1. Identify the major themes and trends across the articles.
2. Highlight the most important insights and their practical implications.
3. Suggest 3–5 concrete action steps the reader can take this week.
4. Note open questions or areas to watch.

Write in clear, direct prose. Start directly with the synthesis — no heading needed. Identify the pattern across articles rather than restating what each one said.
```

- [ ] **Step 5: Create `prompts/sources/hackernews.md`**

```
For HackerNews items: prioritise stories with substantive technical content or high comment signal (active discussion indicates significance). Lead with the core finding or announcement. When the article itself is thin, note that the HN discussion may be the value.
```

- [ ] **Step 6: Create `prompts/sources/reddit.md`**

```
For Reddit posts: note the subreddit as context for the audience. Prioritise posts with substantive text content or links to primary sources. A high upvote score signals broad community consensus; a controversial post signals active debate worth surfacing.
```

- [ ] **Step 7: Create `prompts/sources/bluesky.md`**

```
For Bluesky posts: introduce the author by full name and role/company — do not use @ handles in the digest body. Skip promotional posts. 2–4 sentences per person. Lead with bold predictions, contrarian takes, or concrete technical observations. Name any tools or demos mentioned with links. Focus on original opinions, not commentary on others' work.
```

- [ ] **Step 8: Create `prompts/sources/feeds.md`**

```
For blog posts and RSS articles: lead with the announcement, finding, or insight directly — do not open with "this post discusses" or "the author argues". Name specific products, features, metrics, and benchmarks explicitly. Include one direct quote if it crystallises the point (max 125 characters). Cover practical implications: API changes, new capabilities, policy shifts. Avoid structural summaries ("the author first explains X, then covers Y").
```

- [ ] **Step 9: Create `prompts/sources/github_trending.md`**

```
For GitHub Trending repositories: explain what the project does and why it is gaining traction now. Include the primary tech stack if relevant. Omit projects trending purely due to social virality with no technical substance.
```

- [ ] **Step 10: Create `prompts/sources/web_search.md`**

```
For web search results: treat as supplementary context. Prefer primary sources (official blogs, papers, documentation) over aggregators or reposts. If a search result covers a story already present from another source, merge them rather than listing separately.
```

- [ ] **Step 11: Create `prompts/sources/youtube.md`**

```
For YouTube and podcast content: open with "The Takeaway" — one sentence maximum capturing the single most important idea from this video. Introduce the speaker by full name and why their perspective matters (role, company, track record). Extract 3–4 substantive, counterintuitive points (200–400 words total). Include one direct quote that captures their voice (max 125 characters). Close with a one-sentence insight tying the lessons together. Avoid meta-commentary like "in this episode" or "the host asks".
```

- [ ] **Step 12: Create `prompts/sources/twitter.md`**

```
For Twitter/X posts: introduce the author by full name and role/company — do not use @ handles in the digest body. Skip retweets and replies. 2–4 sentences per person. Lead with bold predictions, contrarian takes, or concrete technical observations. Name any tools, demos, or papers mentioned with links. Focus on original opinions, not commentary on others' work.
```

- [ ] **Step 13: Verify all files exist**

```bash
find prompts -name "*.md" | sort
```
Expected output (11 files):
```
prompts/deepdive_analyse.md
prompts/deepdive_synthesise.md
prompts/digest.md
prompts/sources/bluesky.md
prompts/sources/feeds.md
prompts/sources/github_trending.md
prompts/sources/hackernews.md
prompts/sources/reddit.md
prompts/sources/twitter.md
prompts/sources/web_search.md
prompts/sources/youtube.md
```

- [ ] **Step 14: Commit**

```bash
git add prompts/
git commit -m "feat: add prompt files for digest, deepdive, and all source types"
```

---

## Task 3: Wire digest.py to use prompt files

**Files:**
- Modify: `knowledge_tracker/generators/digest.py`
- Create: `tests/test_generators.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_generators.py
from unittest.mock import patch, MagicMock, call
from knowledge_tracker.generators.digest import generate
from knowledge_tracker.models import Article

HN_ARTICLE = Article(
    url="https://example.com/rag",
    title="RAG Overview",
    description="About RAG.",
    source="hackernews",
    score=200,
)
FEED_ARTICLE = Article(
    url="https://blog.com/post",
    title="Blog Post",
    description="A blog post.",
    source="feed",
    score=0,
)

MOCK_RESPONSE = MagicMock()
MOCK_RESPONSE.content = [
    MagicMock(type="tool_use", input={"digest_body": "## Top Stories\n", "sources_failed": []})
]


def test_generate_loads_digest_prompt():
    """digest.generate() must load prompts/digest.md as the system prompt."""
    with (
        patch("knowledge_tracker.generators.digest.load_prompt", return_value="system") as mock_load,
        patch("knowledge_tracker.generators.digest.load_source_prompt", return_value=None),
        patch("knowledge_tracker.generators.digest.call_with_retry", return_value=MOCK_RESPONSE),
    ):
        generate(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            articles=[HN_ARTICLE], prefs={},
            date="2026-01-01", sources_fetched=["hackernews"],
        )
        mock_load.assert_called_once_with("digest")


def test_generate_appends_source_prompt_to_system():
    """Per-source prompt is appended to the system string passed to call_with_retry."""
    captured = {}

    def capture_call(client, **kwargs):
        captured["system"] = kwargs.get("system", "")
        return MOCK_RESPONSE

    with (
        patch("knowledge_tracker.generators.digest.load_prompt", return_value="base"),
        patch("knowledge_tracker.generators.digest.load_source_prompt", return_value="HN rules"),
        patch("knowledge_tracker.generators.digest.call_with_retry", side_effect=capture_call),
    ):
        generate(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            articles=[HN_ARTICLE], prefs={},
            date="2026-01-01", sources_fetched=["hackernews"],
        )
    assert "HN rules" in captured["system"]


def test_generate_skips_source_prompt_when_none():
    """Sources with no prompt file are silently skipped — no KeyError or crash."""
    with (
        patch("knowledge_tracker.generators.digest.load_prompt", return_value="base"),
        patch("knowledge_tracker.generators.digest.load_source_prompt", return_value=None),
        patch("knowledge_tracker.generators.digest.call_with_retry", return_value=MOCK_RESPONSE),
    ):
        # Should not raise
        result = generate(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            articles=[HN_ARTICLE], prefs={},
            date="2026-01-01", sources_fetched=["hackernews"],
        )
    assert result["body"] == "## Top Stories\n"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_generators.py -v
```
Expected: `ImportError` or `AssertionError` — `load_prompt` not yet imported in digest.py

- [ ] **Step 3: Update `knowledge_tracker/generators/digest.py`**

Replace the file content:

```python
import logging
import anthropic
from knowledge_tracker.models import Article
from knowledge_tracker.claude_client import call_with_retry
from knowledge_tracker.prompt_loader import load_prompt, load_source_prompt

logger = logging.getLogger(__name__)

DIGEST_TOOL = {
    "name": "generate_digest",
    "description": "Generate a structured daily digest of articles for a topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "digest_body": {
                "type": "string",
                "description": (
                    "Full markdown body of the digest (no frontmatter). "
                    "Start with a '### Highlights' section: 3-5 bullet points, each one sentence on the most significant thing happening in the topic today — no links, no source attribution, just the insight. "
                    "Then group articles into thematic sections using #### headings with an emoji: "
                    "e.g. '#### 🔥 Top Stories', '#### 🛠️ Tools & Releases', '#### 💡 Practical Tips', "
                    "'#### 📚 Tutorials & Guides', '#### 🤔 Research & Concepts', '#### 🔗 Worth Bookmarking'. "
                    "Use whatever sections fit the day's content; omit empty ones; invent new ones as needed. "
                    "Each article: '**title** — one sentence (what it is and why it matters). [{source}](url)'. "
                    "No horizontal rules between articles. Do NOT add #deepdive tags."
                ),
            },
            "sources_failed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of source names that returned no articles.",
            },
        },
        "required": ["digest_body", "sources_failed"],
    },
}


def _build_system_prompt(articles: list[Article]) -> str:
    """Load base digest prompt and append per-source instructions for sources present."""
    system = load_prompt("digest")
    present_sources = sorted({a.source for a in articles})
    source_sections = []
    for source in present_sources:
        src_prompt = load_source_prompt(source)
        if src_prompt:
            label = source.replace("_", " ").title()
            source_sections.append(f"### {label}\n{src_prompt}")
    if source_sections:
        system += "\n\n## Per-Source Instructions\n\n" + "\n\n".join(source_sections)
    return system


def generate(
    client: anthropic.Anthropic,
    *,
    model: str,
    topic: dict,
    articles: list[Article],
    prefs: dict,
    date: str,
    sources_fetched: list[str],
) -> dict:
    """Generate a daily digest for one topic. Returns dict with body and metadata."""
    if not articles:
        return {"body": "*No articles found today.*\n", "sources_fetched": sources_fetched, "sources_failed": []}

    system = _build_system_prompt(articles)

    articles_text = "\n\n".join(
        f"**[{i+1}] [{a.title}]({a.url})**\n"
        f"Source: {a.source} | Score: {a.score}\n"
        f"{a.description[:300]}"
        for i, a in enumerate(articles)
    )

    prefs = prefs or {}
    pref_lines = []
    if prefs.get("positive_keywords"):
        pref_lines.append(f"Preferred keywords: {', '.join(prefs['positive_keywords'])}")
    if prefs.get("preferred_domains"):
        pref_lines.append(f"Trusted sources: {', '.join(prefs['preferred_domains'][:10])}")
    if prefs.get("negative_keywords"):
        pref_lines.append(f"Suppress topics: {', '.join(prefs['negative_keywords'])}")
    pref_block = ("\n\nReader preferences (use to bias selection and tone):\n" + "\n".join(pref_lines)) if pref_lines else ""

    prompt = f"""Generate a daily digest for the topic: **{topic['name']}**
Date: {date} | Keywords: {', '.join(topic.get('keywords', []))}
{pref_block}

Today's articles (already deduplicated and scored by relevance):

{articles_text}

Instructions:
- Open with a '### Highlights' section: 3-5 bullets, each one sentence capturing the most significant thing happening in the topic today. No links or source attribution — pure signal.
- Then group into thematic sections (#### with emoji). Omit any section with nothing strong to include.
- Merge items covering the same story into one entry; include all relevant links.
- Each entry: bold plain title, em dash, one sentence on what it is and why it matters, then [source](url) at the end.
- Rank by signal value, not score. Do NOT add #deepdive tags.
"""

    response = call_with_retry(
        client,
        model=model,
        max_tokens=4096,
        system=system,
        tools=[DIGEST_TOOL],
        messages=[{"role": "user", "content": prompt}],
        tool_choice={"type": "tool", "name": "generate_digest"},
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use:
        logger.error("No tool_use block in digest response")
        return {"body": "*Generation failed.*\n", "sources_fetched": sources_fetched, "sources_failed": []}

    result = tool_use.input
    return {
        "body": result["digest_body"],
        "sources_fetched": sources_fetched,
        "sources_failed": result.get("sources_failed", []),
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_generators.py tests/test_integration.py -v
```
Expected: all pass (integration tests mock `call_with_retry` and are unaffected by the system prompt change)

- [ ] **Step 5: Commit**

```bash
git add knowledge_tracker/generators/digest.py tests/test_generators.py
git commit -m "feat: load digest system prompt and per-source instructions from prompt files"
```

---

## Task 4: Wire deepdive.py to use prompt files

**Files:**
- Modify: `knowledge_tracker/generators/deepdive.py`
- Modify: `tests/test_generators.py` (append tests)

- [ ] **Step 1: Add failing tests to `tests/test_generators.py`**

Append to the existing file:

```python
from knowledge_tracker.generators.deepdive import analyse_article, synthesise
from knowledge_tracker.models import Article

SAMPLE_ARTICLE = Article(
    url="https://example.com/rag",
    title="RAG Overview",
    description="About RAG.",
    source="hackernews",
    score=100,
)

MOCK_PHASE1_RESPONSE = MagicMock()
MOCK_PHASE1_RESPONSE.content = [MagicMock(type="tool_use", input={
    "summary": "RAG is useful.",
    "key_insights": ["insight"],
    "research_expansion": "More research.",
    "keywords": ["RAG"],
})]

MOCK_SYNTH_RESPONSE = MagicMock()
MOCK_SYNTH_RESPONSE.content = [MagicMock(type="text", text="Weekly synthesis.")]


def test_analyse_article_loads_system_prompt():
    """analyse_article must pass system= to call_with_retry using deepdive_analyse.md."""
    captured = {}

    def capture(client, **kwargs):
        captured["system"] = kwargs.get("system")
        return MOCK_PHASE1_RESPONSE

    with (
        patch("knowledge_tracker.generators.deepdive.load_prompt", return_value="analyse instructions"),
        patch("knowledge_tracker.generators.deepdive.call_with_retry", side_effect=capture),
    ):
        analyse_article(
            MagicMock(), model="m",
            article=SAMPLE_ARTICLE,
            topic={"name": "T", "keywords": ["RAG"]},
        )
    assert captured["system"] == "analyse instructions"


def test_synthesise_loads_system_prompt():
    """synthesise must pass system= to call_with_retry using deepdive_synthesise.md."""
    captured = {}

    def capture(client, **kwargs):
        captured["system"] = kwargs.get("system")
        return MOCK_SYNTH_RESPONSE

    with (
        patch("knowledge_tracker.generators.deepdive.load_prompt", return_value="synth instructions"),
        patch("knowledge_tracker.generators.deepdive.call_with_retry", side_effect=capture),
    ):
        synthesise(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            analyses=[{"summary": "s", "key_insights": [], "research_expansion": "", "_title": "t"}],
            week_start="2026-03-16",
            week_end="2026-03-22",
        )
    assert captured["system"] == "synth instructions"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_generators.py::test_analyse_article_loads_system_prompt tests/test_generators.py::test_synthesise_loads_system_prompt -v
```
Expected: FAIL — `load_prompt` not imported in deepdive.py

- [ ] **Step 3: Update `knowledge_tracker/generators/deepdive.py`**

Add import at top and `system=` parameter to both calls:

```python
import logging
import anthropic
from knowledge_tracker.models import Article
from knowledge_tracker.claude_client import call_with_retry
from knowledge_tracker.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

PHASE1_TOOL = {
    "name": "analyse_article",
    "description": "Analyse a single article and produce structured research output.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2–3 sentence summary of the article's main argument.",
            },
            "key_insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3–5 key insights or takeaways.",
            },
            "research_expansion": {
                "type": "string",
                "description": "150–250 word expansion: what related work exists, open questions, practical implications.",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5–10 topic keywords extracted from this article for preference learning.",
            },
        },
        "required": ["summary", "key_insights", "research_expansion", "keywords"],
    },
}


def analyse_article(
    client: anthropic.Anthropic,
    *,
    model: str,
    article: Article,
    topic: dict,
    article_text: str = "",
) -> dict:
    """Phase 1: analyse one article. Returns structured JSON dict."""
    content = article_text or article.description or article.title
    prompt = f"""Analyse this article for the topic **{topic['name']}**.

Title: {article.title}
URL: {article.url}
Content:
{content[:3000]}

Topic keywords: {', '.join(topic.get('keywords', []))}"""

    try:
        response = call_with_retry(
            client,
            model=model,
            max_tokens=2048,
            system=load_prompt("deepdive_analyse"),
            tools=[PHASE1_TOOL],
            messages=[{"role": "user", "content": prompt}],
            tool_choice={"type": "tool", "name": "analyse_article"},
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use:
            return tool_use.input
    except Exception as e:
        logger.warning("Phase 1 analysis failed for %s: %s", article.url, e)

    return {
        "summary": article.description[:200],
        "key_insights": [],
        "research_expansion": "",
        "keywords": [],
    }


def synthesise(
    client: anthropic.Anthropic,
    *,
    model: str,
    topic: dict,
    analyses: list[dict],
    week_start: str,
    week_end: str,
) -> str:
    """Phase 2: synthesise all analyses into a weekly narrative."""
    analyses_text = "\n\n".join(
        f"### Article {i+1}: {a.get('_title', '')}\n"
        f"Summary: {a.get('summary', '')}\n"
        f"Key insights: {'; '.join(a.get('key_insights', []))}\n"
        f"Research expansion: {a.get('research_expansion', '')}"
        for i, a in enumerate(analyses)
    )

    prompt = f"""You have analysed {len(analyses)} articles on **{topic['name']}** from {week_start} to {week_end}.

Here are the per-article analyses:

{analyses_text}

Suggest 3–5 concrete action steps the reader can take this week. Note open questions or areas to watch."""

    try:
        response = call_with_retry(
            client,
            model=model,
            max_tokens=2048,
            system=load_prompt("deepdive_synthesise"),
            tools=[],
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((b for b in response.content if b.type == "text"), None)
        if text_block:
            return text_block.text
    except Exception as e:
        logger.warning("Synthesis failed: %s", e)

    return "*Synthesis unavailable.*"


def format_deepdive_body(
    analyses: list[dict],
    articles: list[Article],
    synthesis: str,
    week_start: str,
    week_end: str,
    topic: dict,
) -> str:
    """Format the full deep dive markdown body."""
    parts = [
        f"# {topic['name']} — Week of {week_start}\n",
        f"**Period:** {week_start} → {week_end}  ",
        f"**Articles reviewed:** {len(articles)}\n",
        "---\n",
        "## Synthesis\n",
        synthesis,
        "\n---\n",
        "## Article Deep Dives\n",
    ]

    for i, (article, analysis) in enumerate(zip(articles, analyses)):
        insights = "\n".join(f"- {ins}" for ins in analysis.get("key_insights", []))
        parts.append(
            f"### {i+1}. [{article.title}]({article.url})\n\n"
            f"**Summary:** {analysis.get('summary', '')}\n\n"
            f"**Key Insights:**\n{insights}\n\n"
            f"**Research Expansion:**\n{analysis.get('research_expansion', '')}\n\n"
            f"---\n"
        )

    return "\n".join(parts)
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add knowledge_tracker/generators/deepdive.py tests/test_generators.py
git commit -m "feat: load deepdive system prompts from prompt files"
```

---

## Task 5: builders.yaml + config loader

**Files:**
- Create: `config/builders.yaml`
- Modify: `knowledge_tracker/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add failing tests to `tests/test_config.py`**

Read the current `tests/test_config.py` first, then append:

```python
# Append to tests/test_config.py
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_config.py -v -k "builders"
```
Expected: `ImportError` — `load_builders_config` not yet defined

- [ ] **Step 3: Add `load_builders_config` to `knowledge_tracker/config.py`**

Append to the existing file (do not modify `load_config`):

```python
def load_builders_config(path: str = "config/builders.yaml") -> dict:
    """Load the curated builder list. Returns {} if the file does not exist."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}
```

- [ ] **Step 4: Create `config/builders.yaml`**

```yaml
# config/builders.yaml
# Global curated builder list applied across all topics.
# Twitter and YouTube sources only activate when credentials are set.
# Full Twitter account IDs from: https://github.com/zarazhangrui/follow-builders

twitter:
  accounts:
    - handle: karpathy
      id: "33836629"
      name: Andrej Karpathy
    - handle: sama
      id: "12631042"
      name: Sam Altman
    - handle: swyx
      id: "549057890"
      name: swyx
    - handle: rauchg
      id: "18988"
      name: Guillermo Rauch
    - handle: petergyang
      id: "14226776"
      name: Peter Yang
    - handle: levie
      id: "7517999"
      name: Aaron Levie
    - handle: AndrewYNg
      id: "15358364"
      name: Andrew Ng
    - handle: emollick
      id: "24733248"
      name: Ethan Mollick
    - handle: kanjun
      id: "118557511"
      name: Kanjun Qiu
    - handle: alexandr_wang
      id: "3336027"
      name: Alexandr Wang
    - handle: GaryMarcus
      id: "17632388"
      name: Gary Marcus
    - handle: ylecun
      id: "226744807"
      name: Yann LeCun
    - handle: demishassabis
      id: "3347058"
      name: Demis Hassabis
    - handle: drfeifei
      id: "1551395060"
      name: Fei-Fei Li
    - handle: hardmaru
      id: "26809117"
      name: David Ha
    - handle: ilyasut
      id: "1234817"
      name: Ilya Sutskever
    - handle: gdb
      id: "29883836"
      name: Greg Brockman
    - handle: jdh
      id: "14543457"
      name: Jonathan Hoefler
    - handle: miramurati
      id: "1098503768"
      name: Mira Murati
    - handle: scaling01
      id: "1430468569936580614"
      name: Dario Amodei
    - handle: danielgross
      id: "7893532"
      name: Daniel Gross
    - handle: benedictevans
      id: "35609905"
      name: Benedict Evans
    - handle: pmarca
      id: "rachelwithers"
      name: Marc Andreessen
    - handle: sama
      id: "12631042"
      name: Sam Altman
    - handle: naval
      id: "745273"
      name: Naval Ravikant

youtube:
  channels:
    - id: UCXZCJLdBC09xxGZ6gcdrc6A
      name: Latent Space
    - id: UCqd7KBQN0XuEFKCHOTKiHtw
      name: No Priors
    - id: UCCezIgC97LvombAt4RHs_7w
      name: Lex Fridman
    - id: UCbmNph6atAoGfqLoCL_duAg
      name: Andrej Karpathy
    - id: UCGq-a57w-aPwyi3pW7XLiHw
      name: Machine Learning Street Talk

blogs:
  feeds:
    - url: https://www.anthropic.com/news.rss
      name: Anthropic News
    - url: https://openai.com/blog/rss
      name: OpenAI Blog
    - url: https://karpathy.github.io/feed.xml
      name: Andrej Karpathy
    - url: https://eugeneyan.com/rss.xml
      name: Eugene Yan
    - url: https://lilianweng.github.io/index.xml
      name: Lilian Weng
    - url: https://simonwillison.net/atom/everything/
      name: Simon Willison
    - url: https://www.interconnects.ai/feed
      name: Interconnects (Nathan Lambert)
    - url: https://hamel.dev/rss.xml
      name: Hamel Husain
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_config.py -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add knowledge_tracker/config.py config/builders.yaml tests/test_config.py
git commit -m "feat: add builders.yaml and load_builders_config()"
```

---

## Task 6: YouTube source

**Files:**
- Create: `knowledge_tracker/sources/youtube.py`
- Create: `tests/test_sources/test_youtube.py`
- Modify: `knowledge_tracker/sources/__init__.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sources/test_youtube.py
import respx
import httpx
import pytest
from knowledge_tracker.sources.youtube import fetch


MOCK_VIDEOS_RESPONSE = {
    "data": [
        {
            "id": "abc123xyz",
            "title": "The Future of AI Agents",
            "publishedAt": "2026-03-25T14:00:00Z",
            "description": "Episode summary here.",
        }
    ]
}

MOCK_TRANSCRIPT_RESPONSE = {
    "content": "Welcome to Latent Space. Today we discuss agent architectures..."
}


@respx.mock
def test_fetch_returns_articles_when_api_key_set(monkeypatch):
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    respx.get("https://api.supadata.ai/v1/youtube/channel/videos").mock(
        return_value=httpx.Response(200, json=MOCK_VIDEOS_RESPONSE)
    )
    respx.get("https://api.supadata.ai/v1/youtube/transcript").mock(
        return_value=httpx.Response(200, json=MOCK_TRANSCRIPT_RESPONSE)
    )
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert len(articles) == 1
    assert articles[0].title == "The Future of AI Agents"
    assert articles[0].source == "youtube"
    assert articles[0].author == "Latent Space"
    assert "agent architectures" in articles[0].description
    assert articles[0].url == "https://www.youtube.com/watch?v=abc123xyz"


def test_fetch_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("SUPADATA_API_KEY", raising=False)
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert articles == []


@respx.mock
def test_fetch_returns_empty_on_api_error(monkeypatch):
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    respx.get("https://api.supadata.ai/v1/youtube/channel/videos").mock(
        return_value=httpx.Response(500)
    )
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert articles == []


@respx.mock
def test_fetch_falls_back_to_description_on_transcript_failure(monkeypatch):
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    respx.get("https://api.supadata.ai/v1/youtube/channel/videos").mock(
        return_value=httpx.Response(200, json=MOCK_VIDEOS_RESPONSE)
    )
    respx.get("https://api.supadata.ai/v1/youtube/transcript").mock(
        return_value=httpx.Response(404)
    )
    articles = fetch([{"id": "UCXZCJLdBC09xxGZ6gcdrc6A", "name": "Latent Space"}])
    assert len(articles) == 1
    assert articles[0].description == "Episode summary here."
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_sources/test_youtube.py -v
```
Expected: `ModuleNotFoundError: No module named 'knowledge_tracker.sources.youtube'`

- [ ] **Step 3: Implement `knowledge_tracker/sources/youtube.py`**

```python
import logging
import os
from datetime import datetime, timezone, timedelta
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
SUPADATA_BASE = "https://api.supadata.ai/v1"


def fetch(channels: list[dict]) -> list[Article]:
    """Fetch recent YouTube video transcripts via Supadata. Returns [] if SUPADATA_API_KEY not set."""
    api_key = os.environ.get("SUPADATA_API_KEY")
    if not api_key:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    articles = []

    for channel in channels:
        try:
            articles.extend(_fetch_channel(channel, cutoff, api_key))
        except Exception as e:
            logger.warning("YouTube fetch failed for channel %s: %s", channel.get("name"), e)

    return articles


def _fetch_channel(channel: dict, cutoff: datetime, api_key: str) -> list[Article]:
    headers = {"x-api-key": api_key}
    channel_id = channel["id"]
    channel_name = channel.get("name", channel_id)

    resp = httpx.get(
        f"{SUPADATA_BASE}/youtube/channel/videos",
        params={"id": channel_id, "limit": 10},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()

    articles = []
    for video in resp.json().get("data", []):
        published_str = video.get("publishedAt", "")
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if published < cutoff:
            continue

        try:
            t_resp = httpx.get(
                f"{SUPADATA_BASE}/youtube/transcript",
                params={"videoId": video["id"]},
                headers=headers,
                timeout=30,
            )
            t_resp.raise_for_status()
            description = t_resp.json().get("content", "")[:3000]
        except Exception:
            description = video.get("description", "")[:500]

        articles.append(Article(
            url=f"https://www.youtube.com/watch?v={video['id']}",
            title=video.get("title", ""),
            description=description,
            source="youtube",
            author=channel_name,
            score=0,
        ))

    return articles
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_sources/test_youtube.py -v
```
Expected: 4 passed

- [ ] **Step 5: Add youtube to `knowledge_tracker/sources/__init__.py`**

```python
from knowledge_tracker.sources import (
    hackernews,
    reddit,
    web_scraper,
    web_search,
    github_trending,
    bluesky,
    youtube,
    twitter,
)
```

(Note: twitter is added here too — implement it in Task 7 before this import works. Do Task 7 before committing this change.)

- [ ] **Step 6: Commit** (after Task 7 is also done — see note in Task 7)

---

## Task 7: Twitter/X source

**Files:**
- Create: `knowledge_tracker/sources/twitter.py`
- Create: `tests/test_sources/test_twitter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sources/test_twitter.py
import respx
import httpx
import pytest
from knowledge_tracker.sources.twitter import fetch

MOCK_TWEETS_RESPONSE = {
    "data": [
        {
            "id": "1234567890",
            "text": "Exciting progress on inference-time compute scaling today. Here's what matters...",
            "created_at": "2026-03-26T10:00:00Z",
        }
    ]
}


@respx.mock
def test_fetch_returns_articles_when_token_set(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    respx.get("https://api.twitter.com/2/users/33836629/tweets").mock(
        return_value=httpx.Response(200, json=MOCK_TWEETS_RESPONSE)
    )
    accounts = [{"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"}]
    articles = fetch(accounts)
    assert len(articles) == 1
    assert articles[0].source == "twitter"
    assert articles[0].author == "Andrej Karpathy"
    assert articles[0].url == "https://twitter.com/karpathy/status/1234567890"


def test_fetch_returns_empty_without_token(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    accounts = [{"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"}]
    assert fetch(accounts) == []


@respx.mock
def test_fetch_returns_empty_on_api_error(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    respx.get("https://api.twitter.com/2/users/33836629/tweets").mock(
        return_value=httpx.Response(429)
    )
    accounts = [{"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"}]
    assert fetch(accounts) == []


@respx.mock
def test_fetch_handles_multiple_accounts(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "test-token")
    respx.get("https://api.twitter.com/2/users/33836629/tweets").mock(
        return_value=httpx.Response(200, json=MOCK_TWEETS_RESPONSE)
    )
    respx.get("https://api.twitter.com/2/users/12631042/tweets").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    accounts = [
        {"id": "33836629", "handle": "karpathy", "name": "Andrej Karpathy"},
        {"id": "12631042", "handle": "sama", "name": "Sam Altman"},
    ]
    articles = fetch(accounts)
    assert len(articles) == 1  # sama had no tweets
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_sources/test_twitter.py -v
```
Expected: `ModuleNotFoundError: No module named 'knowledge_tracker.sources.twitter'`

- [ ] **Step 3: Implement `knowledge_tracker/sources/twitter.py`**

```python
import logging
import os
from datetime import datetime, timezone, timedelta
import httpx
from knowledge_tracker.models import Article

logger = logging.getLogger(__name__)
X_API_BASE = "https://api.twitter.com/2"


def fetch(accounts: list[dict]) -> list[Article]:
    """Fetch recent tweets from curated accounts via X API v2. Returns [] if X_BEARER_TOKEN not set."""
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"Authorization": f"Bearer {token}"}
    articles = []

    for account in accounts:
        try:
            articles.extend(_fetch_account(account, cutoff, headers))
        except Exception as e:
            logger.warning("Twitter fetch failed for @%s: %s", account.get("handle"), e)

    return articles


def _fetch_account(account: dict, cutoff: str, headers: dict) -> list[Article]:
    user_id = account["id"]
    resp = httpx.get(
        f"{X_API_BASE}/users/{user_id}/tweets",
        params={
            "max_results": 5,
            "start_time": cutoff,
            "exclude": "retweets,replies",
            "tweet.fields": "created_at",
        },
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()

    articles = []
    for tweet in resp.json().get("data", []):
        text = tweet["text"]
        tweet_id = tweet["id"]
        handle = account["handle"]
        articles.append(Article(
            url=f"https://twitter.com/{handle}/status/{tweet_id}",
            title=text[:100],
            description=text,
            source="twitter",
            author=account.get("name", handle),
            score=0,
        ))

    return articles
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_sources/test_twitter.py -v
```
Expected: 4 passed

- [ ] **Step 5: Update `knowledge_tracker/sources/__init__.py`**

```python
from knowledge_tracker.sources import (
    hackernews,
    reddit,
    web_scraper,
    web_search,
    github_trending,
    bluesky,
    youtube,
    twitter,
)
```

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add knowledge_tracker/sources/youtube.py knowledge_tracker/sources/twitter.py \
        knowledge_tracker/sources/__init__.py \
        tests/test_sources/test_youtube.py tests/test_sources/test_twitter.py
git commit -m "feat: add YouTube (Supadata) and Twitter/X source modules"
```

---

## Task 8: Wire new sources + builder feeds into run.py

**Files:**
- Modify: `run.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Add failing integration test**

Append to `tests/test_integration.py`:

```python
def test_builder_feeds_merged_into_fetch(cfg, vault):
    """Builder blog feeds from builders.yaml are included in the feeds fetch."""
    from unittest.mock import call as mock_call

    mock_embeddings = np.array([[0.1] * 384] * 2)
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = mock_embeddings

    builders_cfg = {
        "blogs": {
            "feeds": [
                {"url": "https://eugeneyan.com/rss.xml", "name": "Eugene Yan"},
            ]
        }
    }

    captured_feeds = {}

    original_fetch_feeds = run_module.sources.web_scraper.fetch_feeds

    def capture_fetch_feeds(feeds):
        captured_feeds["feeds"] = feeds
        return []

    with (
        patch("knowledge_tracker.config.load_builders_config", return_value=builders_cfg),
        patch.object(run_module.sources.web_scraper, "fetch_feeds", side_effect=capture_fetch_feeds),
        patch("knowledge_tracker.generators.digest.call_with_retry", return_value=MOCK_CLAUDE_RESPONSE),
        patch("knowledge_tracker.dedup._get_model", return_value=mock_embedder),
        patch("knowledge_tracker.preferences.scorer.SentenceTransformer", return_value=mock_embedder),
        patch("sentence_transformers.SentenceTransformer", return_value=mock_embedder),
        patch("anthropic.Anthropic"),
        patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}),
    ):
        # Enable feeds in topic config so fetch_feeds is called
        cfg["topics"][0]["sources"]["feeds"] = ["https://existing.com/rss.xml"]
        run_module.run_daily(cfg)

    assert "https://eugeneyan.com/rss.xml" in captured_feeds.get("feeds", [])
    assert "https://existing.com/rss.xml" in captured_feeds.get("feeds", [])
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/test_integration.py::test_builder_feeds_merged_into_fetch -v
```
Expected: FAIL

- [ ] **Step 3: Update `run.py`**

Add `load_builders_config` import and update `_fetch_all_sources` and `run_daily`/`run_weekly`:

```python
# At top of file, add to existing imports:
from knowledge_tracker.config import load_config, load_builders_config

# Replace _fetch_all_sources signature and feeds section:
def _fetch_all_sources(topic: dict, cfg: dict, builders_cfg: dict | None = None) -> tuple[list[Article], list[str], list[str]]:
    """Fetch from all configured sources for a topic. Returns (articles, fetched, failed)."""
    topic_sources = topic.get("sources", {})
    fetched, failed = [], []
    all_articles: list[Article] = []

    # Hacker News
    if topic_sources.get("hackernews"):
        try:
            arts = sources.hackernews.fetch(keywords=topic["keywords"])
            all_articles.extend(arts)
            fetched.append("hackernews")
        except Exception as e:
            logger.warning("HN fetch failed: %s", e)
            failed.append("hackernews")

    # Reddit
    reddit_cfg = topic_sources.get("reddit")
    if reddit_cfg:
        subreddits = reddit_cfg.get("subreddits", [])
        if subreddits:
            try:
                arts = sources.reddit.fetch(subreddits=subreddits)
                all_articles.extend(arts)
                fetched.append("reddit")
            except Exception as e:
                logger.warning("Reddit fetch failed: %s", e)
                failed.append("reddit")

    # Feeds (topic RSS feeds + global builder blog feeds merged)
    topic_feeds = topic_sources.get("feeds", [])
    builder_feed_urls = [f["url"] for f in (builders_cfg or {}).get("blogs", {}).get("feeds", [])]
    all_feeds = topic_feeds + builder_feed_urls
    if all_feeds:
        try:
            arts = sources.web_scraper.fetch_feeds(all_feeds)
            all_articles.extend(arts)
            fetched.append("feeds")
        except Exception as e:
            logger.warning("Feed fetch failed: %s", e)
            failed.append("feeds")

    # GitHub Trending
    gh_cfg = topic_sources.get("github_trending")
    if gh_cfg is not None:
        language = gh_cfg.get("language", "") if isinstance(gh_cfg, dict) else ""
        try:
            arts = sources.github_trending.fetch(language=language)
            all_articles.extend(arts)
            fetched.append("github_trending")
        except Exception as e:
            logger.warning("GitHub Trending fetch failed: %s", e)
            failed.append("github_trending")

    # Bluesky
    bsky_cfg = topic_sources.get("bluesky")
    if bsky_cfg:
        handle = os.environ.get("BLUESKY_HANDLE", "")
        password = os.environ.get("BLUESKY_APP_PASSWORD", "")
        if handle and password:
            try:
                arts = sources.bluesky.fetch(
                    hashtags=bsky_cfg.get("hashtags", []),
                    accounts=bsky_cfg.get("accounts", []),
                    handle=handle,
                    password=password,
                )
                all_articles.extend(arts)
                fetched.append("bluesky")
            except Exception as e:
                logger.warning("Bluesky fetch failed: %s", e)
                failed.append("bluesky")

    # Web search
    if topic_sources.get("web_search"):
        provider = cfg.get("web_search_provider", "tavily")
        try:
            query = " ".join(topic["keywords"])
            arts = sources.web_search.fetch(query=query, provider=provider)
            all_articles.extend(arts)
            fetched.append("web_search")
        except Exception as e:
            logger.warning("Web search failed: %s", e)
            failed.append("web_search")

    # YouTube (optional — requires SUPADATA_API_KEY)
    youtube_channels = (builders_cfg or {}).get("youtube", {}).get("channels", [])
    if youtube_channels:
        try:
            arts = sources.youtube.fetch(youtube_channels)
            if arts:
                all_articles.extend(arts)
                fetched.append("youtube")
        except Exception as e:
            logger.warning("YouTube fetch failed: %s", e)
            failed.append("youtube")

    # Twitter/X (optional — requires X_BEARER_TOKEN)
    twitter_accounts = (builders_cfg or {}).get("twitter", {}).get("accounts", [])
    if twitter_accounts:
        try:
            arts = sources.twitter.fetch(twitter_accounts)
            if arts:
                all_articles.extend(arts)
                fetched.append("twitter")
        except Exception as e:
            logger.warning("Twitter fetch failed: %s", e)
            failed.append("twitter")

    return all_articles, fetched, failed
```

Also update `run_daily` and `run_weekly` to load and pass `builders_cfg`:

```python
def run_daily(cfg: dict) -> None:
    today = date.today().isoformat()
    vault_path = cfg["obsidian_vault"]["local_path"]
    digests_folder = cfg["obsidian_vault"]["digests_folder"]
    prefs_file = cfg["obsidian_vault"]["preferences_file"]
    model = cfg.get("claude_model", "claude-sonnet-4-6")
    max_articles = cfg.get("max_articles_per_digest", 20)
    threshold = cfg.get("dedup_similarity_threshold", 0.85)

    client = anthropic.Anthropic()
    embedder = _get_model()
    builders_cfg = load_builders_config()         # NEW

    for topic in cfg["topics"]:
        slug = topic["slug"]
        logger.info("Processing topic: %s", topic["name"])

        raw_articles, fetched, failed = _fetch_all_sources(topic, cfg, builders_cfg)  # NEW arg
        # ... rest unchanged ...
```

```python
def run_weekly(cfg: dict) -> None:
    # ... existing setup ...
    builders_cfg = load_builders_config()         # NEW (unused in weekly, but consistent)
    # ... rest unchanged — weekly does not call _fetch_all_sources ...
```

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest -v
```
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_integration.py
git commit -m "feat: wire YouTube, Twitter, and builder feeds into daily pipeline"
```

---

## Task 9: README updates

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README to find insertion point**

```bash
grep -n "Optional\|Sources\|API" README.md | head -20
```

- [ ] **Step 2: Add Optional Sources section**

After the existing "Configuration" section (before "Running" or "GitHub Actions"), insert:

```markdown
## Optional Sources

### YouTube & Podcasts

Fetches transcripts from YouTube channels listed in `config/builders.yaml` via the [Supadata API](https://supadata.ai).

1. Get a Supadata API key at [supadata.ai](https://supadata.ai)
2. Add to your `.env`:
   ```
   SUPADATA_API_KEY=your_key_here
   ```
3. Edit `config/builders.yaml` to add or remove channels under `youtube.channels`. Each entry needs an `id` (YouTube channel ID) and `name`.

When `SUPADATA_API_KEY` is not set, the YouTube source is silently skipped.

### Twitter / X

Fetches recent tweets from curated builder accounts listed in `config/builders.yaml` via the [X API v2](https://developer.twitter.com/en/docs/twitter-api).

1. Apply for a free X Developer account at [developer.twitter.com](https://developer.twitter.com)
2. Create a project and app, then copy the Bearer Token
3. Add to your `.env`:
   ```
   X_BEARER_TOKEN=your_bearer_token_here
   ```
4. Edit `config/builders.yaml` to add or remove accounts under `twitter.accounts`. Each entry needs a `handle`, numeric `id`, and `name`. To find a user's numeric ID, use [tweeterid.com](https://tweeterid.com).

When `X_BEARER_TOKEN` is not set, the Twitter source is silently skipped.
```

- [ ] **Step 3: Verify the README renders cleanly**

```bash
uv run python -c "import pathlib; print(pathlib.Path('README.md').read_text()[:500])"
```
Expected: no errors, first 500 chars look correct

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add Optional Sources section for YouTube and Twitter setup"
```

---

## Self-Review Checklist

| Spec requirement | Covered by |
|-----------------|-----------|
| Prompt files in `prompts/` directory | Tasks 1–2 |
| `digest.py` uses `load_prompt("digest")` | Task 3 |
| Per-source prompts appended for present sources | Task 3 |
| `deepdive.py` uses `load_prompt("deepdive_analyse")` | Task 4 |
| `deepdive.py` uses `load_prompt("deepdive_synthesise")` | Task 4 |
| Missing prompt file raises `FileNotFoundError` | Task 1 (`load_prompt` implementation) |
| YouTube source via Supadata | Task 6 |
| YouTube returns `[]` when `SUPADATA_API_KEY` absent | Task 6 |
| Twitter source via X API v2 | Task 7 |
| Twitter returns `[]` when `X_BEARER_TOKEN` absent | Task 7 |
| `config/builders.yaml` with curated list | Task 5 |
| Builder feeds merged into topic feeds at fetch time | Task 8 |
| YouTube channels from `builders.yaml` only | Task 8 |
| Twitter accounts from `builders.yaml` only | Task 8 |
| README with optional source setup docs | Task 9 |
| Prompt content adapted from follow-builders | Tasks 2 (bluesky, feeds, youtube, twitter prompts) |
