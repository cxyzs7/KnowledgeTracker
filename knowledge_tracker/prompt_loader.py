from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str, prompts_dir: Path | None = None) -> str:
    """Load a top-level prompt file. Raises FileNotFoundError if absent."""
    base = prompts_dir if prompts_dir is not None else PROMPTS_DIR
    path = base / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text().strip()


def load_source_prompt(source: str, prompts_dir: Path | None = None) -> str | None:
    """Load a per-source prompt file. Returns None if no prompt exists for this source.
    Raises FileNotFoundError if the sources/ subdirectory itself is missing."""
    base = prompts_dir if prompts_dir is not None else PROMPTS_DIR
    sources_dir = base / "sources"
    if not sources_dir.is_dir():
        raise FileNotFoundError(f"Sources prompt directory not found: {sources_dir}")
    path = sources_dir / f"{source}.md"
    if not path.exists():
        return None
    return path.read_text().strip()
