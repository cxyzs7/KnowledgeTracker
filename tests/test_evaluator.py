from unittest.mock import MagicMock, patch
from knowledge_tracker.generators.evaluator import evaluate
from knowledge_tracker.models import Article

SAMPLE_ARTICLE = Article(
    url="https://example.com/rag",
    title="RAG Overview",
    description="About RAG systems.",
    source="hackernews",
    score=200,
)

MOCK_EVAL_RESPONSE = MagicMock()
MOCK_EVAL_RESPONSE.content = [
    MagicMock(
        type="tool_use",
        input={
            "quality_groundedness": 4,
            "quality_specificity": 3,
            "quality_coverage": 5,
            "quality_format": 4,
            "quality_rationale": "Strong coverage; one vague highlight bullet.",
        },
    )
]


def test_evaluate_returns_scores_on_success():
    with patch("knowledge_tracker.generators.evaluator.call_with_retry", return_value=MOCK_EVAL_RESPONSE):
        result = evaluate(
            MagicMock(),
            model="claude-sonnet-4-6",
            articles=[SAMPLE_ARTICLE],
            digest_body="### Highlights\n- RAG improves retrieval.\n\n#### 🔥 Top Stories\n**RAG Overview** — summary. [hackernews](https://example.com/rag)",
        )
    assert result["quality_groundedness"] == 4
    assert result["quality_specificity"] == 3
    assert result["quality_coverage"] == 5
    assert result["quality_format"] == 4
    assert isinstance(result["quality_rationale"], str)


def test_evaluate_returns_empty_dict_on_api_failure():
    with patch("knowledge_tracker.generators.evaluator.call_with_retry", side_effect=Exception("500 API error")):
        result = evaluate(
            MagicMock(),
            model="claude-sonnet-4-6",
            articles=[SAMPLE_ARTICLE],
            digest_body="### Highlights\n- RAG is useful.",
        )
    assert result == {}


def test_evaluate_passes_articles_and_digest_to_claude():
    captured = {}

    def capture_call(client, **kwargs):
        captured["messages"] = kwargs.get("messages", [])
        captured["tool_choice"] = kwargs.get("tool_choice")
        captured["system"] = kwargs.get("system", "")
        return MOCK_EVAL_RESPONSE

    with patch("knowledge_tracker.generators.evaluator.call_with_retry", side_effect=capture_call):
        evaluate(
            MagicMock(),
            model="claude-sonnet-4-6",
            articles=[SAMPLE_ARTICLE],
            digest_body="Digest content here.",
        )

    prompt_text = captured["messages"][0]["content"]
    assert "RAG Overview" in prompt_text          # article title appears in prompt
    assert "Digest content here." in prompt_text  # digest body appears in prompt
    assert captured["tool_choice"] == {"type": "tool", "name": "evaluate_digest"}
    assert "observe" in captured["system"]        # system prompt is forwarded
