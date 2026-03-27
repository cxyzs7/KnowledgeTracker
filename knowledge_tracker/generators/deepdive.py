import logging
import anthropic
from knowledge_tracker.models import Article
from knowledge_tracker.claude_client import call_with_retry
from knowledge_tracker.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

PHASE1_TOOL = {
    "name": "analyse_article",
    "description": "Analyse a single article and produce structured research output.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2–3 sentence summary of the article's main argument.",
            },
            "key_insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3–5 key insights or takeaways.",
            },
            "research_expansion": {
                "type": "string",
                "description": "150–250 word expansion: what related work exists, open questions, practical implications.",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "5–10 topic keywords extracted from this article for preference learning.",
            },
        },
        "required": ["summary", "key_insights", "research_expansion", "keywords"],
    },
}


def analyse_article(
    client: anthropic.Anthropic,
    *,
    model: str,
    article: Article,
    topic: dict,
    article_text: str = "",
) -> dict:
    """Phase 1: analyse one article. Returns structured JSON dict."""
    content = article_text or article.description or article.title
    prompt = f"""Analyse this article for the topic **{topic['name']}**.

Title: {article.title}
URL: {article.url}
Content:
{content[:3000]}

Topic keywords: {', '.join(topic.get('keywords', []))}"""

    try:
        response = call_with_retry(
            client,
            model=model,
            max_tokens=2048,
            system=load_prompt("deepdive_analyse"),
            tools=[PHASE1_TOOL],
            messages=[{"role": "user", "content": prompt}],
            tool_choice={"type": "tool", "name": "analyse_article"},
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use:
            return tool_use.input
    except Exception as e:
        logger.warning("Phase 1 analysis failed for %s: %s", article.url, e)

    return {
        "summary": article.description[:200],
        "key_insights": [],
        "research_expansion": "",
        "keywords": [],
    }


def synthesise(
    client: anthropic.Anthropic,
    *,
    model: str,
    topic: dict,
    analyses: list[dict],
    week_start: str,
    week_end: str,
) -> str:
    """Phase 2: synthesise all analyses into a weekly narrative."""
    analyses_text = "\n\n".join(
        f"### Article {i+1}: {a.get('_title', '')}\n"
        f"Summary: {a.get('summary', '')}\n"
        f"Key insights: {'; '.join(a.get('key_insights', []))}\n"
        f"Research expansion: {a.get('research_expansion', '')}"
        for i, a in enumerate(analyses)
    )

    prompt = f"""You have analysed {len(analyses)} articles on **{topic['name']}** from {week_start} to {week_end}.

Here are the per-article analyses:

{analyses_text}

Suggest 3–5 concrete action steps the reader can take this week. Note open questions or areas to watch."""

    try:
        response = call_with_retry(
            client,
            model=model,
            max_tokens=2048,
            system=load_prompt("deepdive_synthesise"),
            tools=[],
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((b for b in response.content if b.type == "text"), None)
        if text_block:
            return text_block.text
    except Exception as e:
        logger.warning("Synthesis failed: %s", e)

    return "*Synthesis unavailable.*"


def format_deepdive_body(
    analyses: list[dict],
    articles: list[Article],
    synthesis: str,
    week_start: str,
    week_end: str,
    topic: dict,
) -> str:
    """Format the full deep dive markdown body."""
    parts = [
        f"# {topic['name']} — Week of {week_start}\n",
        f"**Period:** {week_start} → {week_end}  ",
        f"**Articles reviewed:** {len(articles)}\n",
        "---\n",
        "## Synthesis\n",
        synthesis,
        "\n---\n",
        "## Article Deep Dives\n",
    ]

    for i, (article, analysis) in enumerate(zip(articles, analyses)):
        insights = "\n".join(f"- {ins}" for ins in analysis.get("key_insights", []))
        parts.append(
            f"### {i+1}. [{article.title}]({article.url})\n\n"
            f"**Summary:** {analysis.get('summary', '')}\n\n"
            f"**Key Insights:**\n{insights}\n\n"
            f"**Research Expansion:**\n{analysis.get('research_expansion', '')}\n\n"
            f"---\n"
        )

    return "\n".join(parts)
