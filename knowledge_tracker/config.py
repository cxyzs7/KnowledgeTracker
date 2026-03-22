import os
import yaml
from pathlib import Path


def load_config(path: str, validate_env: bool = False) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(p) as f:
        cfg = yaml.safe_load(f)

    # Apply flag_tag default per topic
    for topic in cfg.get("topics", []):
        topic.setdefault("flag_tag", "#deepdive")

    # Vault path: VAULT_PATH env var overrides local_path
    vault_env = os.environ.get("VAULT_PATH")
    if vault_env:
        cfg["obsidian_vault"]["local_path"] = vault_env

    if validate_env:
        _validate_env(cfg)

    return cfg


def _validate_env(cfg: dict) -> None:
    provider = cfg.get("web_search_provider", "tavily")
    key_map = {"tavily": "TAVILY_API_KEY", "exa": "EXA_API_KEY"}
    key = key_map.get(provider)
    if key and not os.environ.get(key):
        raise EnvironmentError(
            f"web_search_provider is '{provider}' but {key} env var is not set"
        )
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY env var is not set")
