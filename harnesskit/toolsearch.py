"""Module 3: deferred tool loading. Hidden tools are found by keyword, then become callable."""
from __future__ import annotations

import math
import re
from typing import Callable


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class ToolIndex:
    """BM25-style ranking without length normalization. Good enough for a few dozen tools."""

    def __init__(self, specs: dict[str, str]):
        self.docs = {name: tokens(name.replace("_", " ") + " " + desc) for name, desc in specs.items()}

    def search(self, query: str, k: int = 3) -> list[str]:
        q = set(tokens(query))
        n = len(self.docs)
        scores = {}
        for name, doc in self.docs.items():
            s = 0.0
            for term in q:
                df = sum(term in d for d in self.docs.values())
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                s += doc.count(term) * idf
            if s > 0:
                scores[name] = s
        return sorted(scores, key=lambda x: (-scores[x], x))[:k]


def make_tool_search(active: dict[str, Callable], deferred: dict[str, Callable]) -> Callable[[str], str]:
    """active is the same dict the Agent holds. Hits are copied into it, so the next turn sees them."""
    index = ToolIndex({n: (f.__doc__ or n).strip() for n, f in deferred.items()})

    def tool_search(query: str) -> str:
        """Find hidden tools by keyword. Matching tools become callable on the next turn."""
        hits = index.search(query)
        if not hits:
            return "No matching tools."
        for name in hits:
            active[name] = deferred[name]
        return "\n".join(f"{n}: {(deferred[n].__doc__ or n).strip()}" for n in hits)

    return tool_search
