# KnowledgeTracker

A personal knowledge pipeline that generates daily topic digests and weekly deep dives, saved as markdown to your Obsidian vault.

## Features

- **Daily Digest**: Fetches articles from Hacker News, Reddit, RSS feeds, GitHub Trending, Bluesky, and web search. Deduplicates (URL + semantic), scores by relevance, and generates a markdown digest via Claude.
- **Weekly Deep Dive**: Reads articles flagged `#deepdive` (or your custom tag) from the week's digests plus manually added links. Performs per-article research expansion via Claude, then synthesises into a comprehensive weekly report.
- **Preference Learning**: Flagged articles feed back into `preferences.md` in your vault to improve future scoring.
- **Obsidian-native**: Output is standard markdown with YAML frontmatter, compatible with Obsidian tags and links.

## Setup

### 1. Clone and install

```bash
git clone https://github.com/you/KnowledgeTracker.git
cd KnowledgeTracker
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys

cp config/topics.yaml config/my_topics.yaml
# Edit config/my_topics.yaml with your topics, vault path, etc.
```

### 3. Run locally

```bash
python run.py daily
python run.py weekly
```

## GitHub Actions

Set the following repository secrets:

| Secret | Description |
|--------|-------------|
| `VAULT_DEPLOY_KEY` | SSH private key with write access to your vault repo |
| `VAULT_REPO` | SSH URL of your vault repo (e.g. `git@github.com:you/vault.git`) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `TAVILY_API_KEY` | Tavily search API key (or `EXA_API_KEY`) |
| `REDDIT_CLIENT_ID` | Reddit app client ID (optional) |
| `REDDIT_CLIENT_SECRET` | Reddit app client secret (optional) |
| `BLUESKY_HANDLE` | Bluesky handle (optional) |
| `BLUESKY_APP_PASSWORD` | Bluesky app password (optional) |

Workflows run automatically:
- **Daily digest**: every day at 07:00 UTC
- **Weekly deep dive**: every Monday at 08:00 UTC

Trigger manually via the Actions tab → workflow → "Run workflow".

## Configuration

Edit `config/topics.yaml`:

```yaml
obsidian_vault:
  repo: "git@github.com:you/your-vault.git"
  local_path: "/path/to/local/vault"   # overridden by VAULT_PATH env var
  digests_folder: "Digests"
  deepdive_folder: "DeepDives"
  preferences_file: "preferences.md"

claude_model: "claude-sonnet-4-6"
web_search_provider: "tavily"          # or "exa"
max_articles_per_digest: 20
max_articles_deepdive: 15
dedup_similarity_threshold: 0.85

topics:
  - name: "AI Engineering"
    slug: "ai_engineering"
    keywords: ["LLM", "RAG", "agent"]
    reference_links: []
    flag_tag: "#deepdive"
    sources:
      hackernews: true
      reddit:
        subreddits: ["MachineLearning"]
      bluesky:
        hashtags: ["#llm"]
        accounts: []
      github_trending:
        language: ""
      web_search: true
      feeds: []
```

## Output format

### Daily digest (`Digests/<slug>/YYYY-MM-DD.md`)

```markdown
---
date: 2026-03-21
topic: AI Engineering
sources_fetched: [hackernews, reddit]
sources_failed: []
article_count: 12
---

# AI Engineering — Daily Digest · 2026-03-21

## Top Stories

### [Article Title](https://example.com)
*Source: Hacker News · 300 points*
Summary of the article.

#deepdive

---

## Manual Links
<!-- Add links here for weekly deep dive inclusion -->
-
```

### Weekly deep dive (`DeepDives/<slug>/YYYY-MM-DD-week.md`)

Contains a synthesis section, then per-article deep dives with key insights and research expansion.

## Tests

```bash
pytest -v
```
