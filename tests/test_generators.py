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


from knowledge_tracker.generators.deepdive import analyse_article, synthesise

SAMPLE_ARTICLE = Article(
    url="https://example.com/rag",
    title="RAG Overview",
    description="About RAG.",
    source="hackernews",
    score=100,
)

MOCK_PHASE1_RESPONSE = MagicMock()
MOCK_PHASE1_RESPONSE.content = [MagicMock(type="tool_use", input={
    "summary": "RAG is useful.",
    "key_insights": ["insight"],
    "research_expansion": "More research.",
    "keywords": ["RAG"],
})]

MOCK_SYNTH_RESPONSE = MagicMock()
MOCK_SYNTH_RESPONSE.content = [MagicMock(type="text", text="Weekly synthesis.")]


def test_analyse_article_loads_system_prompt():
    """analyse_article must pass system= to call_with_retry using deepdive_analyse.md."""
    captured = {}

    def capture(client, **kwargs):
        captured["system"] = kwargs.get("system")
        return MOCK_PHASE1_RESPONSE

    with (
        patch("knowledge_tracker.generators.deepdive.load_prompt", return_value="analyse instructions"),
        patch("knowledge_tracker.generators.deepdive.call_with_retry", side_effect=capture),
    ):
        analyse_article(
            MagicMock(), model="m",
            article=SAMPLE_ARTICLE,
            topic={"name": "T", "keywords": ["RAG"]},
        )
    assert captured["system"] == "analyse instructions"


def test_synthesise_loads_system_prompt():
    """synthesise must pass system= to call_with_retry using deepdive_synthesise.md."""
    captured = {}

    def capture(client, **kwargs):
        captured["system"] = kwargs.get("system")
        return MOCK_SYNTH_RESPONSE

    with (
        patch("knowledge_tracker.generators.deepdive.load_prompt", return_value="synth instructions"),
        patch("knowledge_tracker.generators.deepdive.call_with_retry", side_effect=capture),
    ):
        synthesise(
            MagicMock(), model="m",
            topic={"name": "T", "keywords": []},
            analyses=[{"summary": "s", "key_insights": [], "research_expansion": "", "_title": "t"}],
            week_start="2026-03-16",
            week_end="2026-03-22",
        )
    assert captured["system"] == "synth instructions"
