import logging
import anthropic
from knowledge_tracker.models import Article
from knowledge_tracker.claude_client import call_with_retry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior engineer curating a daily digest for a developer who wants \
high-signal, actionable content. Your priorities:
- Avoid hype and marketing language. Favour depth and practicality.
- If the same story appears across multiple sources, merge them into one entry and list all relevant links.
- Omit sections that have nothing worth including today.
- Quality over quantity: a tight digest of 10 great items beats 30 mediocre ones."""

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
        body = "*No articles found today.*\n"
        return {"body": body, "sources_fetched": sources_fetched, "sources_failed": []}

    articles_text = "\n\n".join(
        f"**[{i+1}] [{a.title}]({a.url})**\n"
        f"Source: {a.source} | Score: {a.score}\n"
        f"{a.description[:300]}"
        for i, a in enumerate(articles)
    )

    # Build preference context from stored preferences
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
        system=SYSTEM_PROMPT,
        tools=[DIGEST_TOOL],
        messages=[{"role": "user", "content": prompt}],
        tool_choice={"type": "tool", "name": "generate_digest"},
    )

    tool_use = next(
        (b for b in response.content if b.type == "tool_use"),
        None,
    )
    if not tool_use:
        logger.error("No tool_use block in digest response")
        return {"body": "*Generation failed.*\n",
                "sources_fetched": sources_fetched, "sources_failed": []}

    result = tool_use.input
    return {
        "body": result["digest_body"],
        "sources_fetched": sources_fetched,
        "sources_failed": result.get("sources_failed", []),
    }
