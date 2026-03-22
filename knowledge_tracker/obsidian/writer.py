import os
import yaml


def write_digest(
    vault_path: str,
    folder: str,
    topic_slug: str,
    date: str,
    frontmatter: dict,
    body: str,
) -> str:
    dir_path = os.path.join(vault_path, folder, topic_slug)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{date}.md")

    fm = yaml.dump({"date": date, **frontmatter}, default_flow_style=False, allow_unicode=True)
    manual_section = "\n## Manual Links\n<!-- Add links here for weekly deep dive inclusion -->\n<!-- Format: - [optional title](url) or bare URL on its own line -->\n-\n"
    content = f"---\n{fm}---\n\n{body}\n{manual_section}"

    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def write_deepdive(
    vault_path: str,
    folder: str,
    topic_slug: str,
    week_start: str,
    frontmatter: dict,
    body: str,
) -> str:
    dir_path = os.path.join(vault_path, folder, topic_slug)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f"{week_start}-week.md")

    fm = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    content = f"---\n{fm}---\n\n{body}\n"

    with open(filepath, "w") as f:
        f.write(content)
    return filepath
