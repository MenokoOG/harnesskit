"""Module 4: context discovery and threshold compaction with incremental summaries."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

NAMES = ("AGENTS.md", "CLAUDE.md")


def discover_context(start: Path, stop: Path) -> str:
    """Walk from stop (the project root) down to start. In each folder the first filename found wins."""
    start, stop = Path(start).resolve(), Path(stop).resolve()
    chain = []
    for d in [start, *start.parents]:
        chain.append(d)
        if d == stop:
            break
    else:
        raise ValueError(f"{start} is not inside {stop}")
    parts = []
    for d in reversed(chain):
        for name in NAMES:
            f = d / name
            if f.is_file():
                parts.append(f"<ctx path='{f}'>\n{f.read_text(encoding='utf-8')}\n</ctx>")
                break
    return "\n".join(parts)


def estimate_tokens(messages: list[dict]) -> int:
    return sum(len(json.dumps(m)) for m in messages) // 4


def render(messages: list[dict]) -> str:
    return "\n".join(f"{m['role']}: {str(m.get('content', ''))[:500]}" for m in messages)


def compact(messages, summarize: Callable[[str], str], keep_ratio: float = 0.3, previous: str = ""):
    """Keep the system message and a recent tail. Fold everything between into one merged summary."""
    system, body = messages[0], list(messages[1:])
    keep = max(4, int(len(body) * keep_ratio))
    head, tail = body[:-keep], body[-keep:]
    while head and tail and tail[0]["role"] == "tool":  # never split a call from its result
        tail.insert(0, head.pop())
    if not head:
        return messages, previous
    prompt = (
        f"<previous-summary>\n{previous}\n</previous-summary>\n"
        f"<new-messages>\n{render(head)}\n</new-messages>\n"
        "Merge both into one summary. Keep decisions and open problems. Drop details that are no longer true."
    )
    summary = summarize(prompt)
    folded = {"role": "user", "content": f"<summary>\n{summary}\n</summary>"}
    return [system, folded, *tail], summary


@dataclass
class Compactor:
    """Middleware. Fires when the estimated size crosses the threshold."""

    summarize: Callable[[str], str]
    threshold_tokens: int = 100_000
    keep_ratio: float = 0.3
    summary: str = ""

    def __call__(self, agent) -> None:
        if estimate_tokens(agent.messages) < self.threshold_tokens:
            return
        agent.messages, self.summary = compact(agent.messages, self.summarize, self.keep_ratio, self.summary)
