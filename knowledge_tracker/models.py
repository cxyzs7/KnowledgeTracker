from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Article:
    url: str
    title: str
    description: str
    source: str                          # e.g. "hackernews", "reddit"
    author: Optional[str] = None
    score: int = 0                       # engagement score from source (HN points, upvotes)
    embedding: Optional[list[float]] = None
    merged_sources: list[str] = field(default_factory=list)  # other sources covering same story
    flagged_date: Optional[str] = None   # ISO date string, set by reader.py
