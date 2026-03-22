# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install all deps (runtime + dev) into .venv — run after cloning
uv run pytest                    # run full test suite
uv run pytest tests/test_dedup.py            # run a single test file
uv run pytest tests/test_dedup.py::test_url_dedup_removes_duplicates  # run one test
uv run python run.py daily       # run daily digest (requires env vars)
uv run python run.py weekly      # run weekly deep dive (requires env vars)
uv run python run.py daily --config config/topics.yaml  # explicit config path
```

Required env vars at runtime: `ANTHROPIC_API_KEY` + one of `TAVILY_API_KEY` / `EXA_API_KEY`. Source-specific vars (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD`) are optional — missing ones silently skip that source. Set `VAULT_PATH` to override `obsidian_vault.local_path` from the config.

## Architecture

`run.py` is the CLI entry point (not inside the package). `run_daily` and `run_weekly` are the two top-level pipeline functions. Each iterates over all topics in `config/topics.yaml`.

### Daily pipeline (`run_daily`)
1. `_fetch_all_sources` — calls each enabled source in sequence, collects `Article` objects
2. `dedup.url_dedup` → `dedup.semantic_dedup` — first dedup by exact URL, then cluster near-duplicates using `all-MiniLM-L6-v2` cosine similarity (threshold from config, default 0.85)
3. `preferences.scorer.score_and_filter` — scores each article: semantic similarity × 60 pts + structural signals (preferred domain +15, preferred author +15, reference domain +10, negative keyword −25 each), filter out `score <= 0`, cap at `max_articles_per_digest`
4. `generators.digest.generate` — Claude API call (tool_use, `generate_digest` tool) → markdown body string
5. `obsidian.writer.write_digest` — writes `{vault}/{digests_folder}/{slug}/{YYYY-MM-DD}.md` with YAML frontmatter + body + `## Manual Links` section
6. `obsidian.git_sync.sync_vault` — only when `GITHUB_ACTIONS` env var is not set

### Weekly pipeline (`run_weekly`)
1. `obsidian.reader.parse_week_digests` — scans digest files from `today-7d` to `today-1d`, finds articles where the `### [title](url)` section contains `flag_tag` (default `#deepdive`), plus bare/markdown URLs in the `## Manual Links` section
2. For each article: fetch full page text (`web_scraper.fetch_url`), then `generators.deepdive.analyse_article` (Phase 1 tool_use call → `{summary, key_insights, research_expansion, keywords}`)
3. `generators.deepdive.synthesise` — Phase 2 plain-text call over all Phase 1 outputs
4. `generators.deepdive.format_deepdive_body` — assembles final markdown
5. `obsidian.writer.write_deepdive` — writes `{vault}/{deepdive_folder}/{slug}/{week_start}-week.md`
6. `preferences.store.update_preferences` — merges new domains/authors/keywords from Phase 1 `keywords` arrays back into `preferences.md` in the vault

### Key design constraints
- `dedup.semantic_dedup` stores embeddings on `Article.embedding` as a side effect so `scorer.score_and_filter` can reuse them (avoids double-encoding)
- `dedup._model` is a process-global singleton; `sentence_transformers.SentenceTransformer` is imported lazily inside `run_daily` to avoid loading the model on test import
- `preferences.md` lives in the Obsidian vault, not this repo. It has YAML frontmatter keyed by topic `slug` and a human-editable prose body. `store.py` parses with `^---\n(.*?)\n---\n` regex and rewrites the file preserving the body
- `claude_client.call_with_retry` wraps all Claude calls with backoff `[1, 2, 4]s`, respects `Retry-After` headers on 429, re-raises non-retryable 4xx immediately
- When `GITHUB_ACTIONS=true`, `run.py` skips `git_sync` — GitHub Actions handles git commit/push directly in the workflow steps

### Sources
Each source module has a single `fetch()` function (or `fetch_feeds`/`fetch_url` for `web_scraper`) returning `list[Article]`. All failures are caught and logged; they return `[]` rather than raising. `sources/__init__.py` imports all submodules so `run.py` can access them as `sources.hackernews.fetch(...)`.

### Testing patterns
- Source tests use `respx.mock` for httpx-based sources and `unittest.mock.patch` for SDK-based ones (praw, atproto) and feedparser (which uses urllib, not httpx)
- Integration tests in `test_integration.py` patch `run._fetch_all_sources` and `knowledge_tracker.generators.digest.call_with_retry` / `knowledge_tracker.generators.deepdive.call_with_retry` directly; they set `GITHUB_ACTIONS=true` to suppress git sync
- Scorer tests pre-set `article.embedding` to orthogonal vectors when testing negative keyword filtering (mock embedder returns `[1.0, 0.0]` for all encode calls; set article embedding to `[0.0, 1.0]` so cosine sim = 0 and negative keyword penalty drops total below 0)
