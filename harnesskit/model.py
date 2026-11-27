"""The model seam. Any object with a complete() method can drive the harness."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Protocol

_ids = itertools.count(1)


class Model(Protocol):
    def complete(self, messages: list[dict], tools: list[dict]) -> dict: ...


def reply(content: str = "", calls: list[tuple[str, dict]] | None = None, cost: float = 0.0) -> dict:
    """Build one assistant message. calls is a list of (tool name, args)."""
    tool_calls = [{"id": f"call_{next(_ids)}", "name": n, "args": a} for n, a in (calls or [])]
    return {"role": "assistant", "content": content, "tool_calls": tool_calls, "cost": cost}


@dataclass
class FakeModel:
    """Plays back a script of replies and records what it was shown. For offline tests."""

    script: list[dict]
    seen: list[list[dict]] = field(default_factory=list)

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        self.seen.append([dict(m) for m in messages])
        if not self.script:
            raise RuntimeError("FakeModel script exhausted")
        return self.script.pop(0)
