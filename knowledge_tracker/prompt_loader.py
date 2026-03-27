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
    """Load a per-source prompt file. Returns None if no file exists for this source."""
    base = prompts_dir if prompts_dir is not None else PROMPTS_DIR
    path = base / "sources" / f"{source}.md"
    if not path.exists():
        return None
    return path.read_text().strip()
