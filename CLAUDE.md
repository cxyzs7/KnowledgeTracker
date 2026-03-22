# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

KnowledgeTracker is a personal knowledge pipeline. It runs two automated jobs:

- **Daily digest** — fetches articles from Hacker News, Reddit, RSS feeds, GitHub Trending, Bluesky, and web search; deduplicates and scores them by relevance; generates a markdown summary via Claude; and saves it to an Obsidian vault.
- **Weekly deep dive** — reads articles the user flagged (`#deepdive`) during the week, fetches each article's full text, analyses each one with Claude (key insights, research expansion), synthesises across all of them, and writes a comprehensive report to the vault.

Both jobs run automatically via GitHub Actions and can also be triggered locally.

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure your topics and vault

Edit `config/topics.yaml`. The two things that must be set for the system to work:

- `obsidian_vault.local_path` — absolute path to your local Obsidian vault (e.g. `~/Documents/MyVault`). Override with the `VAULT_PATH` env var at runtime.
- `obsidian_vault.repo` — SSH URL of your vault's GitHub repo (used only by GitHub Actions for cloning).

Everything else has sensible defaults. Add or remove topics freely; each topic needs a `name`, `slug` (used as a directory name and preferences key), `keywords`, and a `sources` block.

### 3. Set environment variables

Copy `.env.example` to `.env` and fill in values:

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Digest and deep dive generation |
| `TAVILY_API_KEY` | Yes (or EXA) | Web search source |
| `EXA_API_KEY` | Yes (or Tavily) | Alternative web search |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | No | Reddit source — skipped if absent |
| `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` | No | Bluesky source — skipped if absent |
| `VAULT_PATH` | No | Overrides `local_path` in config (used by GitHub Actions) |

`web_search_provider` in `config/topics.yaml` selects which search key is required (`tavily` or `exa`). The app fails fast at startup with a clear error if the required key is missing.

### 4. Run locally

```bash
uv run python run.py daily
uv run python run.py weekly
```

### 5. Set up GitHub Actions (automated)

In your KnowledgeTracker GitHub repo, add these **secrets** (Settings → Secrets → Actions):

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic key |
| `TAVILY_API_KEY` | Your Tavily key (or `EXA_API_KEY`) |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Reddit app credentials (optional) |
| `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` | Bluesky credentials (optional) |
| `VAULT_DEPLOY_KEY` | SSH **private** key with write access to your vault repo |
| `VAULT_REPO` | SSH URL of your vault repo, e.g. `git@github.com:you/vault.git` |

**Creating the vault deploy key:**
```bash
ssh-keygen -t ed25519 -C "knowledge-tracker-deploy" -f vault_deploy_key -N ""
# Add vault_deploy_key.pub as a Deploy Key (with write access) in your vault repo's Settings
# Add the contents of vault_deploy_key as VAULT_DEPLOY_KEY secret in this repo
```

Schedules: daily digest runs at 07:00 UTC every day; weekly deep dive runs at 08:00 UTC every Monday. Both can be triggered manually via the Actions tab.

---

## Using the system day-to-day

**Reading digests:** Each digest is saved to `{vault}/Digests/{slug}/YYYY-MM-DD.md` with YAML frontmatter. Articles Claude considers strong topic matches are tagged `#deepdive` in the markdown body.

**Flagging articles for the weekly deep dive:** In any digest file, add `#deepdive` on its own line below an article's `### [title](url)` heading. The weekly pipeline picks up all such articles from the past 7 days.

**Adding your own links:** Each digest has a `## Manual Links` section at the bottom. Add bare URLs or `[title](url)` links there — the weekly pipeline picks those up too.

**Tuning what you see:** Edit `preferences.md` in your vault directly. The YAML frontmatter is machine-readable; add domains, authors, or keywords you want boosted or suppressed:

```yaml
---
topics:
  ai_engineering:
    preferred_domains: ["eugeneyan.com", "lilianweng.github.io"]
    preferred_authors: []
    positive_keywords: ["RAG", "evals", "agents"]
    negative_keywords: ["crypto", "web3"]
    reference_links: []
---
```

---

## Commands

```bash
uv sync                                                    # install deps
uv run pytest                                              # full test suite
uv run pytest tests/test_dedup.py                          # single file
uv run pytest tests/test_dedup.py::test_url_dedup_removes_duplicates  # single test
uv run python run.py daily
uv run python run.py weekly
uv run python run.py daily --config config/topics.yaml    # explicit config path
```

---

## Architecture

`run.py` is the CLI entry point (not inside the package). `run_daily` and `run_weekly` are the two top-level pipeline functions, each iterating over all topics in `config/topics.yaml`.

### Daily pipeline (`run_daily`)

1. **`_fetch_all_sources`** — calls each enabled source in sequence; any source that fails returns `[]` and is logged. Returns `(articles, fetched_list, failed_list)`.
2. **`dedup.url_dedup`** — removes exact-URL duplicates, keeping the highest-score article and recording the others in `Article.merged_sources`.
3. **`dedup.semantic_dedup`** — encodes all remaining articles with `all-MiniLM-L6-v2`, computes a cosine similarity matrix, and greedily clusters pairs above `dedup_similarity_threshold` (default 0.85). The highest-score article in each cluster is kept; others are noted in `merged_sources`. **Side effect:** embeddings are stored on each `Article.embedding` for reuse in the scorer.
4. **`preferences.scorer.score_and_filter`** — scores each article using two components:
   - *Semantic* (0–60 pts): cosine similarity between the article embedding and the topic keyword vector, multiplied by 60
   - *Structural* (additive): preferred domain +15, preferred author +15, reference domain +10, each negative keyword match −25
   - Total clamped to [−100, 100]. Articles with `score <= 0` are dropped. Top `max_articles_per_digest` are returned.
5. **`generators.digest.generate`** — sends articles to Claude via the `generate_digest` tool_use call; receives back a markdown body string.
6. **`obsidian.writer.write_digest`** — writes `{vault}/{digests_folder}/{slug}/{YYYY-MM-DD}.md`. Always appends a `## Manual Links` section so the user can add their own links.
7. **`obsidian.git_sync.sync_vault`** — `git pull --rebase` + add + commit + push. **Only runs locally**; when `GITHUB_ACTIONS=true` the workflow handles git directly.

### Weekly pipeline (`run_weekly`)

1. **`obsidian.reader.parse_week_digests`** — globs `{vault}/{digests_folder}/{slug}/*.md` for files dated between `today-7d` and `today-1d`. For each file, splits content into `###` sections and checks for the `flag_tag` (word-boundary regex). Also parses the `## Manual Links` block for bare URLs and `[title](url)` entries. Deduplicates by URL across all files.
2. **Phase 1 per-article** — for each article: `web_scraper.fetch_url` gets the full page text; `generators.deepdive.analyse_article` calls Claude with the `analyse_article` tool to produce `{summary, key_insights, research_expansion, keywords}`.
3. **Phase 2 synthesis** — `generators.deepdive.synthesise` sends all Phase 1 outputs to Claude as plain text (no tool_use) to produce a cross-article narrative with themes and action steps.
4. **`generators.deepdive.format_deepdive_body`** — assembles synthesis + per-article sections into the final markdown body.
5. **`obsidian.writer.write_deepdive`** — writes `{vault}/{deepdive_folder}/{slug}/{week_start}-week.md`.
6. **`preferences.store.update_preferences`** — merges learning signals back into `{vault}/preferences.md`.

### How preference learning works

After each weekly deep dive, `update_preferences` reads the existing `preferences.md` from the vault (or creates it), then:

- **Domains** — extracts the hostname from every deep-dived article's URL and appends it to `preferred_domains` if not already present.
- **Authors** — appends any `Article.author` values to `preferred_authors`.
- **Keywords** — reads the `keywords` array from each Phase 1 Claude output and appends new terms to `positive_keywords`.

The file has two parts: a YAML frontmatter block (machine-written, keyed by topic `slug`) and a prose body below the closing `---` (human-editable in Obsidian, never touched by the code). On next run, the scorer reads `preferred_domains`, `preferred_authors`, `positive_keywords`, and `negative_keywords` from the frontmatter to boost or suppress articles before they reach Claude.

`negative_keywords` is never auto-populated — it is only edited manually. Add terms there to permanently suppress articles mentioning those words.

### Key implementation details

- `dedup._model` is a process-global singleton so `all-MiniLM-L6-v2` is only loaded once per run. `SentenceTransformer` is imported lazily inside `run_daily`/`run_weekly` (not at module level) to avoid the ~2s load time during test collection.
- `claude_client.call_with_retry` retries on 429 (respects `Retry-After` header) and 5xx errors with backoff `[1, 2, 4]s`. Non-retryable 4xx errors raise immediately.
- `preferences.md` is parsed with a `^---\n(.*?)\n---\n` regex. The code rewrites only the frontmatter and preserves the prose body verbatim on every write.

### Sources

Each source module exposes a `fetch()` function returning `list[Article]`. All errors are caught internally; sources return `[]` on failure rather than raising, so a broken source never aborts the whole pipeline. `sources/__init__.py` imports all submodules so `run.py` can call `sources.hackernews.fetch(...)` etc.

### Testing patterns

- httpx-based sources (HN, GitHub Trending, web search, web_scraper): use `respx.mock`
- SDK-based sources (Reddit via praw, Bluesky via atproto) and feedparser (uses urllib, not httpx): use `unittest.mock.patch`
- Integration tests patch `run._fetch_all_sources` and `knowledge_tracker.generators.*.call_with_retry`; set `GITHUB_ACTIONS=true` to suppress git sync
- Scorer negative-keyword test: pre-set `article.embedding = [0.0, 1.0]` so cosine sim with the mock topic vector `[1.0, 0.0]` is 0; negative keyword penalty then makes the total negative and the article gets filtered
