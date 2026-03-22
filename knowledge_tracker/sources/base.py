from typing import Protocol
from knowledge_tracker.models import Article


class Source(Protocol):
    def fetch(self, **kwargs) -> list[Article]:
        ...
