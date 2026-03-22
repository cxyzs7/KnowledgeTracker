import logging
import anthropic
from knowledge_tracker.models import Article
from knowledge_tracker.claude_client import call_with_retry

logger = logging.getLogger(__name__)

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
                    "Start with '## Top Stories', then each article as "
                    "'### [title](url)\\n*Source: {source} · {score} points*\\n{summary}\\n\\n{optional_flag_tag}\\n\\n---'. "
                    "Articles that strongly match the topic should end with '#deepdive' on its own line."
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
    date: str,
    sources_fetched: list[str],
) -> dict:
    """Generate a daily digest for one topic. Returns dict with body and metadata."""
    if not articles:
        body = "## Top Stories\n\n*No articles found today.*\n"
        return {"body": body, "sources_fetched": sources_fetched, "sources_failed": []}

    articles_text = "\n\n".join(
        f"**[{i+1}] [{a.title}]({a.url})**\n"
        f"Source: {a.source} | Score: {a.score}\n"
        f"{a.description[:300]}"
        for i, a in enumerate(articles)
    )

    prompt = f"""You are generating a daily digest for the topic: **{topic['name']}**.

Topic keywords: {', '.join(topic.get('keywords', []))}
Date: {date}

Here are today's articles (already deduplicated and scored):

{articles_text}

Generate a markdown digest:
- Include all articles with a brief 2–3 sentence summary
- For articles that strongly match the topic keywords, add `#deepdive` on its own line after the summary
- Keep each summary focused and informative
- Use the exact tool schema format
"""

    response = call_with_retry(
        client,
        model=model,
        max_tokens=4096,
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
        return {"body": "## Top Stories\n\n*Generation failed.*\n",
                "sources_fetched": sources_fetched, "sources_failed": []}

    result = tool_use.input
    return {
        "body": result["digest_body"],
        "sources_fetched": sources_fetched,
        "sources_failed": result.get("sources_failed", []),
    }
