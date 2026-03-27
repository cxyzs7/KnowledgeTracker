# Follow-Builders Integration Design

**Date:** 2026-03-26
**Status:** Approved
**Inspired by:** [follow-builders](https://github.com/zarazhangrui/follow-builders)

---

## Overview

Incorporate four improvements from the follow-builders repo into KnowledgeTracker:

1. **Prompt file system** — extract hardcoded prompts into editable markdown files, with per-source templates tuned to each content type
2. **YouTube/podcast source** — fetch transcripts via Supadata API (optional)
3. **Twitter/X source** — fetch from curated builder accounts via X API (optional)
4. **Curated builder config** — a global `config/builders.yaml` listing high-signal accounts, channels, and blogs that apply across all topics

Translation/bilingual output is explicitly out of scope for this iteration.

---

## 1. Prompt File System

### Structure

```
prompts/
  digest.md              # main digest assembly instructions
  deepdive_analyse.md    # per-article Phase 1 analysis
  deepdive_synthesise.md # weekly synthesis prose
  sources/
    hackernews.md
    reddit.md
    bluesky.md           # adapted from follow-builders tweet prompt
    feeds.md             # adapted from follow-builders blog prompt
    github_trending.md
    web_search.md
    youtube.md           # from follow-builders podcast prompt
    twitter.md           # from follow-builders tweet prompt
```

### Loading mechanism

`digest.py` loads `prompts/digest.md` as the base system prompt. For each source type present in the article batch, it appends the corresponding `prompts/sources/{source}.md` as a labeled section. Articles are already tagged with their source, so Claude receives both per-source instructions and per-source article groups in a single call — no additional API calls.

`deepdive.py` similarly loads `prompts/deepdive_analyse.md` and `prompts/deepdive_synthesise.md` instead of hardcoded strings.

**Missing file behavior:** If any prompt file is absent, the loader raises `FileNotFoundError` immediately. Silent fallback to hardcoded strings is not permitted — a missing prompt file is a misconfiguration that should fail loudly.

### Content improvements from follow-builders

The existing prompts are general-purpose. Per-source templates add precision:

- **Twitter/Bluesky:** skip retweets, replies, promotional content; lead with bold predictions or contrarian takes; 2–4 sentences per person; introduce by full name + role, not handle
- **Podcast/YouTube:** "The Takeaway" (1 sentence max), 3–4 counterintuitive points, one direct quote ≤125 chars, closing insight; avoid meta-commentary about "the episode"
- **Blog/Feeds:** lead with announcement/finding directly; name specific metrics and benchmarks; practical implications (API changes, new capabilities, policy shifts); one direct quote ≤125 chars

---

## 2. New Sources

### YouTube (`knowledge_tracker/sources/youtube.py`)

- API: Supadata (`https://api.supadata.ai/v1/youtube/transcript`)
- Credential: `SUPADATA_API_KEY` env var — returns `[]` silently if unset
- Channel list: from `config/builders.yaml` (`youtube.channels`) only — no per-topic override
- Lookback: 72 hours
- Output: `Article` with title, channel URL, transcript as description (first 3000 chars)
- Integrates into existing pipeline unchanged (url_dedup → semantic_dedup → score_and_filter)

### Twitter/X (`knowledge_tracker/sources/twitter.py`)

- API: X API v2 (`GET /2/users/:id/tweets`)
- Credential: `X_BEARER_TOKEN` env var — returns `[]` silently if unset
- Account list: from `config/builders.yaml` (`twitter.accounts`)
- Lookback: 24 hours, up to 5 tweets per account
- Filtering: excludes retweets (`RT @`) and replies (text starting with `@`)
- Output: `Article` per tweet with author, text as description, tweet URL
- Integrates into existing pipeline unchanged

### README additions

Two collapsible sections in `README.md` under a new **Optional Sources** heading:

- **YouTube/Podcasts** — how to get a Supadata API key, set `SUPADATA_API_KEY`, add channel IDs to `builders.yaml`
- **Twitter/X** — how to get X API Bearer Token, set `X_BEARER_TOKEN`, note on account IDs vs handles

---

## 3. Curated Builder Config (`config/builders.yaml`)

A new global config file listing high-signal builders. These sources apply across all topics — builder signal is broadly relevant regardless of topic keyword.

```yaml
# config/builders.yaml
# Global list of high-signal builders to follow across all topics.
# Twitter and YouTube sources are only active when the corresponding API credentials are set.

twitter:
  accounts:
    - handle: karpathy
      id: "33836629"
      name: Andrej Karpathy
    - handle: sama
      id: "12631042"
      name: Sam Altman
    - handle: swyx
      id: "NNN"        # real IDs populated from follow-builders default-sources.json at implementation time
      name: swyx
    - handle: rauchg
      id: "NNN"
      name: Guillermo Rauch
    # ... full 25-account list from follow-builders default-sources.json

youtube:
  channels:
    - id: UCXZCJLdBC09xxGZ6gcdrc6A
      name: Latent Space
    - id: UCqd7KBQN0XuEFKCHOTKiHtw
      name: No Priors
    # ... (5 channels from follow-builders default-sources.json)

blogs:
  feeds:
    - url: https://www.anthropic.com/blog.rss
      name: Anthropic Blog
    - url: https://karpathy.github.io/feed.xml
      name: Andrej Karpathy
    - url: https://eugeneyan.com/rss.xml
      name: Eugene Yan
    - url: https://lilianweng.github.io/index.xml
      name: Lilian Weng
    - url: https://simonwillison.net/atom/everything/
      name: Simon Willison
```

Individual topics can still add their own feeds and accounts via `topics.yaml` as before. `builders.yaml` feeds are merged into every topic's feed list at fetch time.

---

## 4. Data Flow Changes

The pipeline shape is unchanged. Two new sources are added at fetch time; one new prompt-loading step replaces hardcoded strings.

```
_fetch_all_sources(topic, cfg, builders_cfg)
  ├─ hackernews, reddit, bluesky, github_trending, web_search, feeds  [unchanged]
  ├─ youtube.fetch(builders_cfg.youtube.channels)    [NEW — skipped if no SUPADATA_API_KEY]
  └─ twitter.fetch(builders_cfg.twitter.accounts)    [NEW — skipped if no X_BEARER_TOKEN]
      ↓
url_dedup → semantic_dedup → score_and_filter        [unchanged]
      ↓
digest.generate(...)
  ├─ Load prompts/digest.md as system prompt         [NEW — replaces hardcoded string]
  ├─ For each source type present in batch:
  │    append prompts/sources/{source}.md            [NEW]
  └─ Claude call with source-tagged article groups   [unchanged structure]
      ↓
writer.write_digest(...)                             [unchanged]
```

Weekly deep dive pipeline, dedup logic, scoring, preference learning, and git sync are all unchanged.

---

## 5. New Files Summary

| Path | Purpose |
|------|---------|
| `config/builders.yaml` | Global curated builder list |
| `prompts/digest.md` | Extracted + refined digest system prompt |
| `prompts/deepdive_analyse.md` | Extracted per-article analysis prompt |
| `prompts/deepdive_synthesise.md` | Extracted synthesis prompt |
| `prompts/sources/hackernews.md` | HN-specific extraction rules |
| `prompts/sources/reddit.md` | Reddit-specific rules |
| `prompts/sources/bluesky.md` | Social post rules (adapted from follow-builders) |
| `prompts/sources/feeds.md` | RSS blog rules (adapted from follow-builders) |
| `prompts/sources/github_trending.md` | GitHub trending rules |
| `prompts/sources/web_search.md` | Web search result rules |
| `prompts/sources/youtube.md` | Transcript rules (from follow-builders) |
| `prompts/sources/twitter.md` | Tweet rules (from follow-builders) |
| `knowledge_tracker/sources/youtube.py` | YouTube source module |
| `knowledge_tracker/sources/twitter.py` | Twitter/X source module |
| `README.md` | Optional source setup instructions (additions only) |

---

## 6. Out of Scope

- Bilingual/translation output
- User-local prompt overrides (`~/.knowledge-tracker/prompts/`)
- Delivery channels (Telegram, email)
- Changes to weekly deep dive pipeline
- Changes to scoring, dedup, or preference learning
