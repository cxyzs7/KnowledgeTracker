import logging
import anthropic
from knowledge_tracker.models import Article
from knowledge_tracker.claude_client import call_with_retry

logger = logging.getLogger(__name__)

_EVALUATE_TOOL = {
    "name": "evaluate_digest",
    "description": "Score a generated digest on four quality dimensions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "quality_groundedness": {
                "type": "integer",
                "description": "1-5: every claim in the digest traces back to a provided article",
            },
            "quality_specificity": {
                "type": "integer",
                "description": "1-5: entries name concrete tools, people, or numbers rather than vague summaries",
            },
            "quality_coverage": {
                "type": "integer",
                "description": "1-5: the most significant articles are represented with no glaring omissions",
            },
            "quality_format": {
                "type": "integer",
                "description": "1-5: highlights section present, thematic sections used correctly, entries well-formed",
            },
            "quality_rationale": {
                "type": "string",
                "description": "one sentence summarising the main quality gap or notable strength",
            },
        },
        "required": [
            "quality_groundedness",
            "quality_specificity",
            "quality_coverage",
            "quality_format",
            "quality_rationale",
        ],
    },
}


def evaluate(
    client: anthropic.Anthropic,
    *,
    model: str,
    articles: list[Article],
    digest_body: str,
) -> dict:
    """Evaluate digest quality against source articles. Returns score dict or {} on failure."""
    try:
        articles_text = "\n\n".join(
            f"[{i + 1}] {a.title} — {a.description[:200]}"
            for i, a in enumerate(articles)
        )
        prompt = (
            f"Source articles provided to the digest generator:\n{articles_text}"
            f"\n\nGenerated digest:\n{digest_body}"
            "\n\nScore the digest on each dimension from 1 (poor) to 5 (excellent)."
        )
        response = call_with_retry(
            client,
            model=model,
            max_tokens=512,
            system="You are a precise quality evaluator. Score only what you can observe in the provided text.",
            tools=[_EVALUATE_TOOL],
            messages=[{"role": "user", "content": prompt}],
            tool_choice={"type": "tool", "name": "evaluate_digest"},
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            logger.warning("evaluator: no tool_use block in response")
            return {}
        return tool_use.input
    except Exception as e:
        logger.warning("Digest evaluation failed: %s", e)
        return {}
