# KnowledgeTracker

A personal knowledge pipeline that generates daily topic digests and weekly deep dives, saved as markdown to your Obsidian vault.

- **Daily digest** — fetches articles from Hacker News, Reddit, RSS feeds, GitHub Trending, and web search; deduplicates and scores by relevance; generates a markdown summary via Claude. Optional credential-gated sources (Bluesky, YouTube, Twitter) are silently skipped when credentials are absent.
- **Weekly deep dive** — reads articles you flagged `#deepdive` during the week, performs per-article research expansion via Claude, synthesises across all of them, and writes a comprehensive report.
- **Preference learning** — your flagged articles automatically improve future scoring. Tune further by editing `preferences.md` in your vault.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- An [Anthropic API key](https://console.anthropic.com/)
- A [Tavily](https://tavily.com/) API key for web search
- An Obsidian vault backed by a GitHub repo

## Installation

```bash
git clone https://github.com/you/KnowledgeTracker.git
cd KnowledgeTracker
uv sync
cp .env.example .env
```

## Configuration

### 1. Edit `config/topics.yaml`

Set your vault path and define your topics:

```yaml
obsidian_vault:
  repo: "git@github.com:you/your-vault.git"   # used by GitHub Actions
  local_path: "/path/to/local/vault"           # your local vault directory
  digests_folder: "Digests"
  deepdive_folder: "DeepDives"
  preferences_file: "preferences.md"

claude_model: "claude-sonnet-4-6"
web_search_provider: "tavily"
max_articles_per_digest: 20
max_articles_deepdive: 15
dedup_similarity_threshold: 0.85

topics:
  - name: "AI Engineering"
    slug: "ai_engineering"          # used as folder name and preferences key
    keywords: ["LLM", "RAG", "agent", "evals"]
    reference_links: []             # example articles that define the topic's style
    flag_tag: "#deepdive"           # Obsidian tag to flag for weekly deep dive
    sources:
      hackernews: true
      reddit:
        subreddits: ["MachineLearning", "LocalLLaMA"]
      bluesky:
        hashtags: ["#llm"]
        accounts: []
      github_trending:
        language: ""
      web_search: true
      feeds: []                     # list of RSS/Atom feed URLs
```

Add as many topics as you like. Each gets its own digest folder and preferences entry.

### 2. Set environment variables

Fill in `.env` (copied from `.env.example`):

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | |
| `TAVILY_API_KEY` | Yes | Required if `web_search_provider` is `tavily` (the default) |
| `BLUESKY_HANDLE` | No | Bluesky source skipped if absent |
| `BLUESKY_APP_PASSWORD` | No | Bluesky source skipped if absent |
| `SUPADATA_API_KEY` | No | YouTube source skipped if absent |
| `X_BEARER_TOKEN` | No | Twitter source skipped if absent |

Required keys cause a startup error if missing. All other sources are silently skipped when their credentials are absent.

### Credential-gated sources

**Bluesky** — configure hashtags and accounts per topic in `config/topics.yaml` under `sources.bluesky`.

**YouTube & Podcasts** — fetches transcripts via the [Supadata API](https://supadata.ai). Get a key at [supadata.ai](https://supadata.ai). Edit `config/builders.yaml` to add or remove channels under `youtube.channels` (each entry needs an `id` and `name`).

**Twitter / X** — fetches recent tweets via the [X API v2](https://developer.twitter.com/en/docs/twitter-api). Apply for a free X Developer account, create a project and app, then copy the Bearer Token. Edit `config/builders.yaml` to add or remove accounts under `twitter.accounts` (each entry needs a `handle`, numeric `id`, and `name` — use [tweeterid.com](https://tweeterid.com) to find numeric IDs).

## Running locally

```bash
uv run python run.py daily    # generate today's digest
uv run python run.py weekly   # generate this week's deep dive
```

Digests are written to `{vault}/Digests/{slug}/YYYY-MM-DD.md`.
Deep dives are written to `{vault}/DeepDives/{slug}/YYYY-MM-DD-week.md`.

Local runs automatically commit and push to your vault repo via `git_sync`.

## GitHub Actions setup

Workflows run on a schedule (daily digest at 07:00 UTC, weekly deep dive at 08:00 UTC every Monday) and can be triggered manually from the Actions tab.

### Create a vault access token

1. Go to GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
2. Set **Repository access** to your vault repo only.
3. Grant **Contents: Read and write** permission.
4. Copy the generated token.

### Add repository secrets

In this repo: Settings → Secrets and variables → Actions → New repository secret.

| Secret | Value |
|---|---|
| `VAULT_TOKEN` | Fine-grained PAT from above |
| `VAULT_REPO` | `owner/repo` of your vault, e.g. `cxyzs7/Vault` |
| `ANTHROPIC_API_KEY` | |
| `TAVILY_API_KEY` | |
| `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` | Optional — Bluesky source skipped if absent |
| `SUPADATA_API_KEY` | Optional — YouTube source skipped if absent |
| `X_BEARER_TOKEN` | Optional — Twitter source skipped if absent |

## Day-to-day usage

### Flagging articles for the weekly deep dive

In a daily digest file, add your `flag_tag` (default `#deepdive`) on its own line below any article heading:

```markdown
### [Some Interesting Article](https://example.com)
*Source: Hacker News · 300 points*
Summary here.

#deepdive
```

### Adding your own links

Each digest has a `## Manual Links` section at the bottom. Add bare URLs or `[title](url)` entries — the weekly pipeline picks these up alongside flagged articles:

```markdown
## Manual Links
- https://example.com/something-i-found
- [Great post](https://example.com/post)
```

### Tuning what you see

`preferences.md` in your vault is auto-updated after each weekly deep dive with domains, authors, and keywords extracted from your flagged articles. Edit it directly in Obsidian to boost or suppress content:

```yaml
---
topics:
  ai_engineering:
    preferred_domains: ["eugeneyan.com", "lilianweng.github.io"]
    preferred_authors: []
    positive_keywords: ["RAG", "evals", "agents"]
    negative_keywords: ["crypto", "web3"]   # articles matching these are filtered out
    reference_links: []
---
```

Only `negative_keywords` requires manual entry — everything else is populated automatically from your reading history.
