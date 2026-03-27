#!/usr/bin/env python3
"""
KnowledgeTracker — CLI entry point.

Usage:
    python run.py daily
    python run.py weekly
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()
from datetime import date, timedelta

import anthropic

from knowledge_tracker.config import load_config
import knowledge_tracker.config as _kt_config
from knowledge_tracker.models import Article
from knowledge_tracker.dedup import url_dedup, semantic_dedup, _get_model
from knowledge_tracker.preferences.store import load_preferences, update_preferences
from knowledge_tracker.preferences.scorer import score_and_filter
from knowledge_tracker.obsidian.writer import write_digest, write_deepdive
from knowledge_tracker.obsidian.reader import parse_week_digests, parse_seen_urls
from knowledge_tracker.generators import digest as digest_gen
from knowledge_tracker.generators import deepdive as deepdive_gen
from knowledge_tracker import sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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
    builders_cfg = _kt_config.load_builders_config()

    for topic in cfg["topics"]:
        slug = topic["slug"]
        logger.info("Processing topic: %s", topic["name"])

        raw_articles, fetched, failed = _fetch_all_sources(topic, cfg, builders_cfg)
        logger.info("Fetched %d raw articles from %s", len(raw_articles), fetched)

        # Deduplicate
        articles = url_dedup(raw_articles)

        # Filter out articles already seen in recent digests
        digest_dir = os.path.join(vault_path, digests_folder, slug)
        seen_urls = parse_seen_urls(digest_dir, lookback_days=cfg.get("dedup_lookback_days", 7))
        articles = [a for a in articles if a.url not in seen_urls]
        logger.info("%d articles after cross-day dedup (%d seen in recent digests)", len(articles), len(seen_urls))

        articles = semantic_dedup(articles, threshold=threshold)

        # Score and filter
        prefs = load_preferences(vault_path, prefs_file, slug)
        articles = score_and_filter(articles, topic, prefs, embedder, max_results=max_articles)
        logger.info("%d articles after scoring/filtering", len(articles))

        # Generate digest via Claude
        result = digest_gen.generate(
            client, model=model, topic=topic,
            articles=articles, prefs=prefs, date=today, sources_fetched=fetched,
        )

        # Write to vault
        write_digest(
            vault_path=vault_path,
            folder=digests_folder,
            topic_slug=slug,
            date=today,
            frontmatter={
                "topic": topic["name"],
                "sources_fetched": result["sources_fetched"],
                "sources_failed": result["sources_failed"],
                "article_count": len(articles),
            },
            body=result["body"],
        )
        logger.info("Wrote digest for %s", slug)

    # Sync vault (local only — GitHub Actions handles git directly)
    if not os.environ.get("GITHUB_ACTIONS"):
        from knowledge_tracker.obsidian.git_sync import sync_vault
        sync_vault(vault_path, f"chore: daily digest {today}")


def run_weekly(cfg: dict) -> None:
    today = date.today()
    week_end = (today - timedelta(days=1)).isoformat()
    week_start = (today - timedelta(days=7)).isoformat()

    vault_path = cfg["obsidian_vault"]["local_path"]
    digests_folder = cfg["obsidian_vault"]["digests_folder"]
    deepdive_folder = cfg["obsidian_vault"]["deepdive_folder"]
    prefs_file = cfg["obsidian_vault"]["preferences_file"]
    model = cfg.get("claude_model", "claude-sonnet-4-6")
    max_articles = cfg.get("max_articles_deepdive", 15)

    client = anthropic.Anthropic()
    builders_cfg = _kt_config.load_builders_config()  # noqa: F841 — not used in weekly pipeline, kept for symmetry

    for topic in cfg["topics"]:
        slug = topic["slug"]
        flag_tag = topic.get("flag_tag", "#deepdive")
        logger.info("Deep dive for topic: %s (%s to %s)", topic["name"], week_start, week_end)

        # Read flagged + manual articles from the week's digests
        digest_dir = os.path.join(vault_path, digests_folder, slug)
        articles = parse_week_digests(digest_dir, week_start, week_end, flag_tag)
        articles = articles[:max_articles]
        logger.info("Found %d flagged/manual articles for deep dive", len(articles))

        if not articles:
            logger.info("No articles to deep dive for %s, skipping", slug)
            continue

        # Phase 1: analyse each article
        analyses = []
        for article in articles:
            article_text = sources.web_scraper.fetch_url(article.url) if article.url else ""
            analysis = deepdive_gen.analyse_article(
                client, model=model, article=article,
                topic=topic, article_text=article_text,
            )
            analysis["_title"] = article.title
            analyses.append(analysis)

        # Phase 2: synthesise
        synthesis = deepdive_gen.synthesise(
            client, model=model, topic=topic,
            analyses=analyses, week_start=week_start, week_end=week_end,
        )

        # Format and write
        body = deepdive_gen.format_deepdive_body(
            analyses=analyses, articles=articles,
            synthesis=synthesis, week_start=week_start,
            week_end=week_end, topic=topic,
        )

        write_deepdive(
            vault_path=vault_path,
            folder=deepdive_folder,
            topic_slug=slug,
            week_start=week_start,
            frontmatter={
                "topic": topic["name"],
                "week_start": week_start,
                "week_end": week_end,
                "articles_reviewed": len(articles),
            },
            body=body,
        )
        logger.info("Wrote deep dive for %s", slug)

        # Update preferences from this week's analyses
        update_preferences(vault_path, prefs_file, slug, analyses, articles)

    if not os.environ.get("GITHUB_ACTIONS"):
        from knowledge_tracker.obsidian.git_sync import sync_vault
        sync_vault(vault_path, f"chore: weekly deep dive {week_start}")


def main() -> None:
    parser = argparse.ArgumentParser(description="KnowledgeTracker")
    parser.add_argument("command", choices=["daily", "weekly"])
    parser.add_argument("--config", default="config/topics.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config, validate_env=True)

    if args.command == "daily":
        run_daily(cfg)
    elif args.command == "weekly":
        run_weekly(cfg)


if __name__ == "__main__":
    main()
