from unittest.mock import patch, MagicMock
from knowledge_tracker.generators.digest import generate
from knowledge_tracker.models import Article

HN_ARTICLE = Article(
    url="https://example.com/rag",
    title="RAG Overview",
    description="About RAG.",
    source="hackernews",
    score=200,
)

MOCK_RESPONSE = MagicMock()
MOCK_RESPONSE.content = [
    MagicMock(type="tool_use", input={"digest_body": "## Top Stories\n", "sources_failed": []})
]


def test_generate_loads_digest_prompt():
    """digest.generate() must load prompts/digest.md as the system prompt."""
    with (
        patch("knowledge_tracker.generators.digest.load_prompt", return_value="system") as mock_load,
        patch("knowledge_tracker.generators.digest.load_source_prompt", return_value=None),
        patch("knowledge_tracker.generators.digest.call_with_retry", return_value=MOCK_RESPONSE),
    ):
        generate(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            articles=[HN_ARTICLE], prefs={},
            date="2026-01-01", sources_fetched=["hackernews"],
        )
        mock_load.assert_called_once_with("digest")


def test_generate_appends_source_prompt_to_system():
    """Per-source prompt is appended to the system string passed to call_with_retry."""
    captured = {}

    def capture_call(client, **kwargs):
        captured["system"] = kwargs.get("system", "")
        return MOCK_RESPONSE

    with (
        patch("knowledge_tracker.generators.digest.load_prompt", return_value="base"),
        patch("knowledge_tracker.generators.digest.load_source_prompt", return_value="HN rules"),
        patch("knowledge_tracker.generators.digest.call_with_retry", side_effect=capture_call),
    ):
        generate(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            articles=[HN_ARTICLE], prefs={},
            date="2026-01-01", sources_fetched=["hackernews"],
        )
    assert "HN rules" in captured["system"]


def test_generate_skips_source_prompt_when_none():
    """Sources with no prompt file are silently skipped — no KeyError or crash."""
    with (
        patch("knowledge_tracker.generators.digest.load_prompt", return_value="base"),
        patch("knowledge_tracker.generators.digest.load_source_prompt", return_value=None),
        patch("knowledge_tracker.generators.digest.call_with_retry", return_value=MOCK_RESPONSE),
    ):
        result = generate(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            articles=[HN_ARTICLE], prefs={},
            date="2026-01-01", sources_fetched=["hackernews"],
        )
    assert result["body"] == "## Top Stories\n"
