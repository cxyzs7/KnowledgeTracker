# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                                             # install all deps (runtime + dev)
uv run pytest                                                       # full test suite
uv run pytest tests/test_dedup.py                                   # single file
uv run pytest tests/test_dedup.py::test_url_dedup_removes_duplicates  # single test
uv run python run.py daily
uv run python run.py weekly
uv run python run.py daily --config config/topics.yaml
```

`pythonpath = ["."]` is set in `pyproject.toml` under `[tool.pytest.ini_options]` — this is what makes `knowledge_tracker` importable during test runs. Do not remove it.

## Architecture and non-obvious constraints

`run.py` is the CLI entry point at the repo root (not inside the package). `run_daily` and `run_weekly` each iterate over all topics in `config/topics.yaml`.

### Data flow: daily pipeline

`_fetch_all_sources` → `url_dedup` → `semantic_dedup` → `score_and_filter` → `digest.generate` → `writer.write_digest` → `git_sync` (local only)

### Data flow: weekly pipeline

`reader.parse_week_digests` → `web_scraper.fetch_url` per article → `deepdive.analyse_article` (Phase 1, per article) → `deepdive.synthesise` (Phase 2, all at once) → `deepdive.format_deepdive_body` → `writer.write_deepdive` → `store.update_preferences`

### Constraints that must not be broken

**Embedding side effect in `dedup.semantic_dedup`**
`semantic_dedup` stores the computed `all-MiniLM-L6-v2` embeddings onto each `Article.embedding` as a side effect. `score_and_filter` reuses them (skipping articles where `embedding is not None`). If you remove this side effect, every article gets encoded twice per run.

**Lazy `SentenceTransformer` import in `run.py`**
`SentenceTransformer` is imported inside `run_daily`/`run_weekly`, not at module level. This prevents the ~2s model load from happening during `pytest` collection. Do not move it to the top of `run.py`. The global singleton `dedup._model` follows the same pattern for the same reason.

**`preferences.md` two-part structure**
The file has a YAML frontmatter block (machine-written) and a prose body below the closing `---` (human-editable in Obsidian). `store.py` parses with `^---\n(.*?)\n---\n` and rewrites the frontmatter on every `update_preferences` call while preserving the body verbatim. Never rewrite the whole file — users edit the body directly in Obsidian.

**`flag_tag` word-boundary regex**
`reader.py` matches the flag tag with `(?<!\S){flag_tag}(?!\S)`. A plain `in` check or `str.find` would match `#deepdive` inside words like `#deepdiveresearch`. The regex ensures it only matches the tag when surrounded by whitespace or at line boundaries.

**Sources return `[]` on failure, never raise**
Every source module wraps its logic in a try/except and returns `[]` on any error. This is intentional — a broken source (auth failure, rate limit, network error) should not abort the whole pipeline. `_fetch_all_sources` in `run.py` tracks which sources failed and records them in the digest frontmatter.

**`GITHUB_ACTIONS` skips `git_sync`**
When `GITHUB_ACTIONS=true`, `run_daily` and `run_weekly` skip calling `obsidian.git_sync.sync_vault`. GitHub Actions handles the git commit/push directly in the workflow steps after `run.py` exits. Running `git_sync` inside Actions would conflict.

### Scoring formula

`score_and_filter` in `preferences/scorer.py`:
- Semantic score (0–60): `cosine_similarity(topic_keyword_vector, article_embedding) × 60`
- Structural score (additive): preferred domain +15, preferred author +15, reference domain +10, each negative keyword match −25
- Total clamped to [−100, 100]. Articles where `total <= 0` are dropped before the `max_results` cap is applied.

### Preference learning

After each weekly deep dive, `store.update_preferences` merges into `preferences.md`:
- `preferred_domains` ← hostname of each deep-dived article URL
- `preferred_authors` ← `Article.author` of each article
- `positive_keywords` ← `keywords` array from each Phase 1 Claude output

`negative_keywords` is **never auto-populated** — it is manual-only. This is intentional; automatically adding suppression terms from Claude output would be unpredictable.

### Claude API calls

All calls go through `claude_client.call_with_retry`. It retries on 429 (respects `Retry-After` response header) and HTTP 5xx with backoff `[1, 2, 4]s`. Non-retryable 4xx errors raise immediately. Generators use `tool_choice={"type": "tool", "name": "..."}` to force structured output; `synthesise` in `deepdive.py` uses a plain text call (no tool) because its output is freeform prose.

## Testing patterns

**Which mock to use for sources:**
- httpx-based (HackerNews, GitHub Trending, web_search, web_scraper): `respx.mock` decorator
- SDK-based (Reddit via `praw`, Bluesky via `atproto`) and `feedparser` (uses `urllib`, not httpx): `unittest.mock.patch`

**Integration tests (`tests/test_integration.py`):**
- Patch `run._fetch_all_sources` to skip all network calls
- Patch `knowledge_tracker.generators.digest.call_with_retry` and `knowledge_tracker.generators.deepdive.call_with_retry` to return mock `Message` objects
- Set `GITHUB_ACTIONS=true` via `patch.dict(os.environ, ...)` to suppress `git_sync`
- Mock `sentence_transformers.SentenceTransformer` at the module level (not `run.SentenceTransformer` — it's imported lazily)

**Scorer negative-keyword test:**
The mock embedder returns `[1.0, 0.0]` for all `encode()` calls. This gives every article cosine similarity 1.0 with the topic vector → semantic score 60. A negative keyword penalty of −25 still leaves 35 > 0, so the article isn't filtered. To test filtering, pre-set `article.embedding = [0.0, 1.0]` before calling `score_and_filter` — cosine sim with topic vector `[1.0, 0.0]` is then 0, and −25 drops the total below 0.
