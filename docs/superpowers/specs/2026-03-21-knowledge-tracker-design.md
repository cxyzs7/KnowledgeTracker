# KnowledgeTracker Design Spec

**Date:** 2026-03-21
**Status:** Approved

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
└── requirements.txt
```

---

## Feature 1: Daily Digest

### Data Flow

```
topics.yaml + preferences.md
        ↓
  fetch from all configured sources (per topic, in parallel)
        ↓
  score & filter articles by relevance
  (topic keywords + reference links + learned preferences)
        ↓
  Claude API generates digest markdown
        ↓
  write to Obsidian vault: Digests/{topic}/{YYYY-MM-DD}.md
        ↓
  git commit & push to vault repo
```

### Sources

| Source | Method |
|---|---|
| Hacker News | HN Algolia API (`hn.algolia.com/api`) |
| Reddit | PRAW library; configured subreddits per topic |
| Substacks / Blogs | RSS/Atom feed polling + HTML scraping |
| GitHub Trending | Scrape `github.com/trending` (no auth required) |
| Bluesky | AT Protocol API; configured hashtags/accounts per topic |
| Web Search | Tavily or Exa API using topic keywords |
| Twitter/X | URL-based scraping via `web_scraper.py` (public pages only; no API) |

Each source fetches independently. If a source fails, it is skipped and the digest notes which sources were unavailable.

### Digest Output Format (`Digests/{topic}/YYYY-MM-DD.md`)

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
-
```

The `## Manual Links` section is a dedicated space for the user to paste URLs they want included in the weekly deep dive.

---

## Feature 2: Weekly Deep Dive

### Data Flow

```
scan last 7 days of Digests/{topic}/*.md files
        ↓
  extract flagged articles (lines/links tagged with configured flag_tag, e.g. #deepdive)
  extract manual links (from ## Manual Links section)
        ↓
  fetch full content of each article (web_scraper.py)
  run web_search to find related work, context, counterarguments per article
        ↓
  Claude: per-article deep dive (summary + key insights + research expansion)
  Claude: cross-article synthesis + practical action steps
        ↓
  write to Obsidian vault: DeepDives/{topic}/YYYY-MM-DD-week.md
        ↓
  update preferences.md with signals from flagged articles
        ↓
  git commit & push to vault repo
```

### Deep Dive Output Format (`DeepDives/{topic}/YYYY-MM-DD-week.md`)

```markdown
---
date: 2026-03-21
topic: AI Engineering
articles_reviewed: 8
manual_links: 2
---

# AI Engineering — Weekly Deep Dive · Week of 2026-03-17

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

### Learning Loop

- After each weekly deep dive, `preferences/store.py` extracts signals from flagged articles and manual links: domains, authors, keywords
- These signals are merged into `preferences.md` in the vault repo
- On each daily digest run, `preferences/scorer.py` reads `preferences.md` and uses it to re-rank candidate articles before passing to Claude
- The user can manually edit `preferences.md` in Obsidian to add negative keywords, remove domains, or add reference links

---

## Configuration (`config/topics.yaml`)

```yaml
obsidian_vault:
  repo: "git@github.com:you/your-vault.git"
  local_path: "/path/to/local/vault"    # used for local runs; ignored in Actions
  digests_folder: "Digests"
  deepdive_folder: "DeepDives"
  preferences_file: "preferences.md"

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

---

## GitHub Actions

### Secrets

| Secret | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API for digest and deep dive generation |
| `VAULT_DEPLOY_KEY` | SSH deploy key with write access to Obsidian vault repo |
| `TAVILY_API_KEY` | Web search (or `EXA_API_KEY` if using Exa) |
| `REDDIT_CLIENT_ID` | Reddit API auth |
| `REDDIT_CLIENT_SECRET` | Reddit API auth |
| `BLUESKY_HANDLE` | Bluesky account handle |
| `BLUESKY_PASSWORD` | Bluesky app password |

GitHub Trending requires no token (public page scrape).

### Workflow: `daily_digest.yml`

- Trigger: `cron: '0 7 * * *'` (7am UTC) + `workflow_dispatch`
- Steps: checkout KnowledgeTracker → checkout vault repo → install deps → `python run.py daily` → commit & push vault changes

### Workflow: `weekly_deepdive.yml`

- Trigger: `cron: '0 8 * * 1'` (8am UTC Monday) + `workflow_dispatch`
- Steps: checkout KnowledgeTracker → checkout vault repo → install deps → `python run.py weekly` → commit & push vault changes (digests + updated `preferences.md`)

---

## Error Handling

- Each source is isolated; failures are caught, logged, and noted in the digest frontmatter (`sources_failed`)
- Claude API failures: retry once, then write a minimal fallback file to ensure vault always gets an entry
- Git push failures: workflow exits non-zero → GitHub Actions notifies via email on failure
- Missing `preferences.md`: scorer falls back to topic config only; `preferences.md` is created fresh on first weekly run

---

## CLI

```bash
python run.py daily              # run all topics daily digest
python run.py daily --topic "AI Engineering"   # single topic
python run.py weekly             # run all topics weekly deep dive
python run.py weekly --topic "AI Engineering"
```

---

## Dependencies

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
| `gitpython` | Git operations for vault sync |
