"""Module 2: stuck detection and mid-run steering. The stop guard lives in verify.py."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .loop import Agent, LimitReached

def signature(call: dict) -> str:
    """Same tool plus same arguments gives the same signature, whatever the key order."""
    blob = call["name"] + json.dumps(call.get("args") or {}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass
class StuckDetector:
    """Middleware. Warn after warn_after identical calls. Halt after halt_after, unless it is 0."""

    warn_after: int = 3
    halt_after: int = 0
    counts: dict = field(default_factory=dict)
    seen: set = field(default_factory=set)  # call ids; a list index goes stale after compaction

    def __call__(self, agent: Agent) -> None:
        warnings = []
        for m in agent.messages:
            if m["role"] != "assistant":
                continue
            for call in m.get("tool_calls") or []:
                if call["id"] in self.seen:
                    continue
                self.seen.add(call["id"])
                sig = signature(call)
                n = self.counts[sig] = self.counts.get(sig, 0) + 1
                if self.halt_after and n >= self.halt_after:
                    raise LimitReached(f"stuck: {call['name']} called {n} times with the same arguments")
                if n >= self.warn_after:
                    warnings.append(f"You made the identical {call['name']} call {n} times. Change your approach.")
        for w in warnings:
            agent.messages.append({"role": "user", "content": w})


def drain_inbox(agent: Agent) -> None:
    """Middleware. Anything the user typed mid-run joins the conversation before the next call."""
    while agent.inbox:
        agent.messages.append({"role": "user", "content": agent.inbox.pop(0)})
