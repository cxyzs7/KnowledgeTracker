# KnowledgeTracker Design Spec

**Date:** 2026-03-21
**Status:** Draft

---

## Overview

KnowledgeTracker is a Python-based personal knowledge pipeline with two core features:

1. **Daily Digest** — fetches content from multiple sources per configured topic, generates a markdown digest, and pushes it to an Obsidian vault backed by GitHub.
2. **Weekly Deep Dive** — reads flagged articles and manually added links from the past week's digests, performs per-article deep research and synthesis, and generates a comprehensive weekly report with practical action steps.

The system learns from user engagement over time: flagged articles and manually added links feed back into a `preferences.md` file in the vault, which improves sourcing accuracy on subsequent runs.

---

## Project Structure

```
KnowledgeTracker/
├── config/
│   └── topics.yaml              # topic definitions, source config, vault paths
├── sources/
│   ├── hackernews.py            # HN Algolia API
│   ├── reddit.py                # Reddit API (PRAW)
│   ├── web_scraper.py           # RSS feeds + HTML scraping (Substacks, blogs, Twitter URLs)
│   ├── web_search.py            # Tavily or Exa API for open web search
│   ├── github_trending.py       # scrapes github.com/trending (no token required)
│   └── bluesky.py               # Bluesky AT Protocol API
├── generators/
│   ├── digest.py                # daily digest generator via Claude API
│   └── deepdive.py              # weekly deep dive generator via Claude API
├── preferences/
│   ├── store.py                 # reads/writes preferences.md in vault repo
│   └── scorer.py                # scores candidate articles against learned preferences
├── obsidian/
│   ├── writer.py                # writes markdown files to vault path
│   ├── reader.py                # parses digest files for flagged tags + manual links
│   └── git_sync.py              # git add/commit/push to vault repo
├── scheduler/
│   └── runner.py                # optional local scheduler via APScheduler
├── .github/workflows/
│   ├── daily_digest.yml         # cron: 7am UTC daily
│   └── weekly_deepdive.yml      # cron: 8am UTC every Monday
├── run.py                       # CLI entry: `python run.py daily` / `python run.py weekly`
└── requirements.txt             # pinned dependencies
```

---

## Feature 1: Daily Digest

### Data Flow

```
topics.yaml + preferences.md (from vault)
        ↓
  fetch from all configured sources (per topic, in parallel)
        ↓
  deduplicate articles by URL across sources
        ↓
  score & rank articles by relevance
  (topic keywords + reference links + learned preferences)
  → cap at max_articles_per_digest (default: 20)
        ↓
  Claude API: one call per digest, all articles passed as structured input
        ↓
  write to Obsidian vault: Digests/{topic-slug}/{YYYY-MM-DD}.md
        ↓
  git_sync.py: commit & push to vault repo
```

### Sources

| Source | Method | Config key |
|---|---|---|
| Hacker News | HN Algolia API (`hn.algolia.com/api`) | `hackernews` |
| Reddit | PRAW library; configured subreddits per topic | `reddit` |
| Substacks / Blogs | RSS/Atom feed polling + HTML scraping | `feeds` |
| GitHub Trending | Scrape `github.com/trending` (no auth required) | `github_trending` |
| Bluesky | AT Protocol API; configured hashtags/accounts per topic | `bluesky` |
| Web Search | Tavily or Exa API using topic keywords | `web_search` |
| Twitter/X | URL-based scraping via `web_scraper.py` (public pages only; manual links only — not a proactive source) | n/a |

Each source fetches independently. If a source fails, it is skipped and the digest notes which sources were unavailable.

**Twitter/X note:** Twitter/X is not a configurable proactive source. It is only fetched when the user manually pastes a Twitter URL into the `## Manual Links` section of a digest file. `web_scraper.py` will attempt to fetch the public page; failure is caught and noted in the deep dive output.

### Deduplication

- Articles are deduplicated by URL after all sources return results.
- If the same URL appears in multiple topics' digests, each topic processes it independently (topics are fully isolated).
- If the same URL is flagged across multiple digest files in a week, it appears only once in the weekly deep dive (deduplicated by URL at read time in `reader.py`).

### Digest Output Format (`Digests/{topic-slug}/YYYY-MM-DD.md`)

```markdown
---
date: 2026-03-21
topic: AI Engineering
sources_fetched: [hackernews, reddit, bluesky, github_trending, web_search]
sources_failed: []
---

# AI Engineering — Daily Digest · 2026-03-21

## Top Stories

### [Article Title](url)
*Source: Hacker News · 342 points*
Brief summary of the article...

#deepdive

---

### [Another Article](url)
*Source: Reddit · r/MachineLearning*
Brief summary...

---

## GitHub Trending

- [repo/name](url) — short description · ⭐ 1.2k today

---

## Manual Links
<!-- Add links here for weekly deep dive inclusion -->
<!-- Format: - [optional title](url) or bare URL on its own line -->
-
```

The `## Manual Links` section is a dedicated space for the user to paste URLs for weekly deep dive inclusion. Each entry is a bare URL or a markdown link on its own line; empty list items (`-` with no URL) are ignored.

---

## Feature 2: Weekly Deep Dive

### Date Range

The weekly deep dive processes digest files from the **7 calendar days of the prior week: Monday through Sunday** (i.e., a Monday 8am run covers the Mon–Sun that just ended). Files are identified by their filename date (`YYYY-MM-DD.md`), not modification time. `week_start` = most recent Monday before today; `week_end` = most recent Sunday before today. If fewer than 7 files exist (e.g., first week of use), all available files are processed. If no files are found, the workflow exits cleanly with a log message and no output is written.

The output filename uses the `week_start` date: `DeepDives/{topic-slug}/{week_start}-week.md` (e.g., `2026-03-16-week.md` for the week of March 16–22).

### Data Flow

```
load topics.yaml (keywords) + preferences.md from vault (preferred domains/keywords/signals)
        ↓
scan Digests/{topic-slug}/*.md for dates in range [week_start .. week_end]
  → per-topic directory only (no cross-topic contamination)
        ↓
  reader.py: extract flagged articles + manual links (deduplicated by URL)
        ↓
  web_scraper.py: fetch full content of each article
        ↓
  web_search.py: 2 search queries per article (related work + counterarguments)
  → cap at max_articles_deepdive (default: 15); excess articles skipped with note
        ↓
  Claude Phase 1: one call per article → structured output with fields:
    summary, key_insights, research_expansion, keywords (3–5 topical keywords)
        ↓
  Claude Phase 2: one synthesis call with all Phase 1 outputs
    + topic keywords from config + preference signals from preferences.md
    → themes + practical action steps
        ↓
  write to Obsidian vault: DeepDives/{topic-slug}/{week_start}-week.md
        ↓
  preferences/store.py: read `keywords` field from Phase 1 outputs → merge into preferences.md
        ↓
  git_sync.py: commit & push to vault repo (deep dive file + updated preferences.md)
```

### `obsidian/reader.py` Parsing Contract

**Flagged articles:** `reader.py` operates only on files in `Digests/{topic-slug}/` — there is no cross-topic scanning. A `###`-level heading followed on any line within its section by the `flag_tag` (e.g., `#deepdive`) marks that article as flagged. The URL is taken from the markdown link in the `###` heading line. The `flag_tag` is matched as a word boundary: it must be preceded and followed by whitespace, end-of-line, or start-of-line (regex: `(?<!\S)#deepdive(?!\S)`) — it will not match if embedded inside a URL or a sentence word.

**Manual links:** All non-empty lines under `## Manual Links` are parsed. Each line may be a bare URL or a `[text](url)` markdown link. Lines that are only `-` or whitespace are skipped. Lines that do not contain a valid URL are skipped and logged as warnings.

**Malformed files:** `reader.py` skips any file that fails to parse and logs the filename and error. The weekly run continues with remaining files.

### Deep Dive Output Format (`DeepDives/{topic-slug}/{week_start}-week.md`)

```markdown
---
date: 2026-03-23
topic: AI Engineering
week_start: 2026-03-16
week_end: 2026-03-22
articles_reviewed: 8
manual_links: 2
---

# AI Engineering — Weekly Deep Dive · Week of 2026-03-16

---

## Article Deep Dives

### 1. [Article Title](url)
**Source:** Hacker News · flagged 2026-03-19

**Summary:** ...

**Key Insights:**
- ...

**Research Expansion:** Related work, context, counterarguments found via web research...

---

## Synthesis

Themes and patterns across this week's flagged articles...

## Practical Action Steps

1. ...
2. ...
```

---

## Preference Learning

### `preferences.md` (stored in Obsidian vault repo)

```markdown
---
updated: 2026-03-21
topics:
  ai_engineering:
    preferred_domains: ["eugeneyan.com", "lilianweng.github.io"]
    preferred_authors: ["@karpathy.bsky.social"]
    positive_keywords: ["RAG", "evals", "agents"]
    negative_keywords: []
    reference_links:
      - "https://example.com/article-i-liked"
---

# My Reading Preferences

Auto-updated weekly from flagged articles. Edit manually to tune.
```

### `preferences/store.py` — Signal Extraction

After each weekly deep dive, `store.py` extracts signals from all flagged articles and manual links:

- **Domains:** extracted from article URLs using `urllib.parse` (e.g., `eugeneyan.com` from `https://eugeneyan.com/writing/...`)
- **Authors:** extracted from article metadata if available (RSS `<author>` field, byline in HTML `<meta name="author">`); Bluesky handle if source is Bluesky
- **Keywords:** extracted by asking Claude to return 3–5 topical keywords per article during the per-article deep dive call (reuses existing output, no extra API call)

**Merging rules:**
- New domains/authors/keywords are appended to existing lists (additive only — no automatic removal)
- Duplicates are deduplicated on write
- The prose body of `preferences.md` is preserved unchanged; only the YAML frontmatter block is rewritten
- Manual edits to frontmatter (e.g., adding negative keywords) are preserved because the full frontmatter is read before merging

### `preferences/scorer.py` — Article Scoring

Scores each candidate article on a 0–100 scale before Claude generation:

| Signal | Points |
|---|---|
| URL domain matches a `preferred_domains` entry | +20 |
| Author matches a `preferred_authors` entry | +20 |
| Title/description contains a `positive_keywords` match | +10 per match, max +30 |
| Title/description contains a `negative_keywords` match | -30 per match |
| URL domain matches a `reference_links` domain (from **both** `topics[].reference_links` in config **and** `preferences.md` frontmatter) | +15 |

Articles with a score ≤ 0 are filtered out entirely. Remaining articles are sorted descending and capped at `max_articles_per_digest`. Scoring runs after URL deduplication and before the Claude call.

---

## Claude API Usage

### Model

Default: `claude-sonnet-4-6`. Configurable via `config/topics.yaml` (`claude_model` key). The same model is used for both digest and deep dive.

### Daily Digest (`generators/digest.py`)

- **One Claude call per topic per day.**
- Input: structured list of up to `max_articles_per_digest` articles (title, URL, source, snippet/description).
- Prompt instructs Claude to: write a brief summary per article (2–3 sentences), group by theme if natural, maintain a neutral informational tone.
- Output is the full digest markdown body (articles section only; frontmatter is written by `writer.py`).

### Weekly Deep Dive (`generators/deepdive.py`)

- **Two Claude call phases per topic per week.**
- Phase 1: one call per article (title, URL, full fetched content, web search results). Prompt: produce a structured output with these explicit sections: `## Summary`, `## Key Insights` (bullet list), `## Research Expansion`, `## Keywords` (comma-separated list of 3–5 topical keywords). `store.py` extracts keywords by parsing the `## Keywords` section from Phase 1 output.
- Phase 2: one synthesis call with all Phase 1 outputs concatenated, plus topic keywords from `topics.yaml` and `positive_keywords`/`reference_links` from `preferences.md`. Prompt: identify cross-article themes, extract practical action steps grounded in the user's focus areas. Output: synthesis + action steps markdown.
- Context budget: each Phase 1 call is capped at ~100k tokens of input (full article text truncated if needed). If an article exceeds the limit, the first 80k tokens are used and a note is appended.

---

## Configuration (`config/topics.yaml`)

```yaml
obsidian_vault:
  repo: "git@github.com:you/your-vault.git"
  local_path: "/path/to/local/vault"    # used for local runs
  digests_folder: "Digests"
  deepdive_folder: "DeepDives"
  preferences_file: "preferences.md"

claude_model: "claude-sonnet-4-6"       # optional override
web_search_provider: "tavily"           # "tavily" or "exa"
max_articles_per_digest: 20             # cap per topic per day
max_articles_deepdive: 15               # cap on flagged articles per weekly deep dive
web_search_queries_per_article: 2       # search queries per article in deep dive

topics:
  - name: "AI Engineering"
    slug: "ai_engineering"
    keywords: ["LLM", "RAG", "agent", "fine-tuning", "evals"]
    reference_links:
      - "https://some-article-you-like.com"
    flag_tag: "#deepdive"
    sources:
      hackernews: true
      reddit:
        subreddits: ["MachineLearning", "LocalLLaMA"]
      bluesky:
        hashtags: ["#llm", "#aiengineering"]
        accounts: []
      github_trending:
        language: ""       # empty = all languages
      web_search: true
      feeds:
        - "https://somesubstack.com/feed"
```

### Vault Path Resolution

- **Local runs:** `obsidian_vault.local_path` from `topics.yaml` is used directly.
- **GitHub Actions runs:** the env var `VAULT_PATH` is set by the workflow to the checkout path (e.g., `${{ github.workspace }}/vault`). If `VAULT_PATH` is set, it overrides `local_path`. `run.py` reads `VAULT_PATH` at startup.

---

## GitHub Actions

### Secrets

| Secret | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API |
| `VAULT_DEPLOY_KEY` | SSH deploy key with write access to Obsidian vault repo |
| `TAVILY_API_KEY` | Web search (or `EXA_API_KEY` if using Exa) |
| `REDDIT_CLIENT_ID` | Reddit API auth |
| `REDDIT_CLIENT_SECRET` | Reddit API auth |
| `BLUESKY_HANDLE` | Bluesky account handle |
| `BLUESKY_PASSWORD` | Bluesky app password |

GitHub Trending requires no token (public page scrape).

### Workflow Structure (both workflows follow this pattern)

```yaml
steps:
  - name: Checkout KnowledgeTracker
    uses: actions/checkout@v4

  - name: Checkout Obsidian vault
    uses: actions/checkout@v4
    with:
      repository: you/your-vault
      ssh-key: ${{ secrets.VAULT_DEPLOY_KEY }}
      path: vault

  - name: Set up Python 3.12
    uses: actions/setup-python@v5
    with:
      python-version: "3.12"

  - name: Install dependencies
    run: pip install -r requirements.txt

  - name: Run digest / deep dive
    env:
      VAULT_PATH: ${{ github.workspace }}/vault
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      # ... other secrets as env vars
    run: python run.py daily   # or weekly

  # daily_digest.yml uses:
  - name: Commit and push vault changes
    run: |
      cd vault
      git config user.name "KnowledgeTracker"
      git config user.email "knowledge-tracker@users.noreply.github.com"
      git pull --rebase origin main
      git add .
      git diff --cached --quiet || git commit -m "KnowledgeTracker: daily digest $(date +%Y-%m-%d)"
      git push

  # weekly_deepdive.yml uses:
  - name: Commit and push vault changes
    run: |
      cd vault
      git config user.name "KnowledgeTracker"
      git config user.email "knowledge-tracker@users.noreply.github.com"
      git pull --rebase origin main
      git add .
      git diff --cached --quiet || git commit -m "KnowledgeTracker: weekly deep dive $(date +%Y-%m-%d)"
      git push
```

**Notes on the workflow:**
- `actions/checkout` with `ssh-key: ${{ secrets.VAULT_DEPLOY_KEY }}` automatically configures the remote's push URL to use the SSH key — no `git remote set-url` step is needed.
- The `git pull --rebase` before commit ensures a local run and a concurrent Actions run do not produce a non-fast-forward conflict; the second writer rebases on top of the first.
- The `git diff --cached --quiet || git commit` guard prevents empty commits on days with no new content.
- **`git_sync.py` is used for local runs only.** `run.py` detects `GITHUB_ACTIONS=true` env var and skips `git_sync.py`. For local runs, `git_sync.py` also runs `git pull --rebase` before pushing.

---

## Error Handling

- Each source is isolated; failures are caught, logged, and noted in the digest frontmatter (`sources_failed`).
- Claude API failures: retry up to **3 times** with exponential backoff (1s, 2s, 4s). Rate-limit errors (`429`) wait for the `Retry-After` header value before retrying. Server errors (`5xx`) use the backoff schedule. After 3 failures, the digest writes a minimal fallback file (`## Error\nDigest generation failed — retried 3 times.`) so the vault always gets a dated entry. For deep dive Phase 1 failures, the article is skipped and noted in the output. For Phase 2 (synthesis) failures, the per-article outputs are written as-is without a synthesis section, with a note appended.
- Git push failures: workflow exits non-zero → GitHub Actions notifies via email on failure.
- Missing `preferences.md`: scorer falls back to topic config only; `preferences.md` is created fresh on first weekly run.
- Article fetch failures in deep dive: the article is included with a note ("content unavailable") and Claude generates what it can from the title/URL alone.

---

## CLI

```bash
python run.py daily                        # run all topics daily digest
python run.py daily --topic "AI Engineering"   # single topic
python run.py weekly                       # run all topics weekly deep dive
python run.py weekly --topic "AI Engineering"
```

---

## Dependencies

All dependencies are pinned in `requirements.txt` (generated via `pip-compile` from `requirements.in`). Python version: **3.12**.

| Package | Purpose |
|---|---|
| `anthropic` | Claude API |
| `praw` | Reddit API |
| `atproto` | Bluesky AT Protocol |
| `tavily-python` | Web search |
| `feedparser` | RSS/Atom feeds |
| `httpx` | HTTP client for scraping |
| `beautifulsoup4` | HTML parsing |
| `pyyaml` | Config parsing |
| `apscheduler` | Optional local scheduler |
| `gitpython` | Git operations for local vault sync |
| `pip-tools` | Dependency pinning (`pip-compile`) |
