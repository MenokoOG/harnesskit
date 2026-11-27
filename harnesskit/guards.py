"""Module 2: stuck detection, a verify-on-stop guard and mid-run steering."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .loop import Agent, LimitReached

EDIT_TOOLS = {"write_file", "search_replace", "edit"}
CODE_SUFFIXES = (".py", ".ts", ".js", ".rs", ".go", ".java")
VERIFY_WORDS = ("pytest", "unittest", "npm test", "cargo test", "go test", "ruff", "mypy", "tsc")


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
    cursor: int = 0

    def __call__(self, agent: Agent) -> None:
        warnings = []
        for m in agent.messages[self.cursor :]:
            if m["role"] != "assistant":
                continue
            for call in m.get("tool_calls") or []:
                sig = signature(call)
                n = self.counts[sig] = self.counts.get(sig, 0) + 1
                if self.halt_after and n >= self.halt_after:
                    raise LimitReached(f"stuck: {call['name']} called {n} times with the same arguments")
                if n >= self.warn_after:
                    warnings.append(f"You made the identical {call['name']} call {n} times. Change your approach.")
        for w in warnings:
            agent.messages.append({"role": "user", "content": w})
        self.cursor = len(agent.messages)


@dataclass
class VerifyOnStop:
    """Stop guard. Veto a final answer when code changed and nothing was run to check it."""

    max_nudges: int = 2
    nudges: int = 0

    def __call__(self, agent: Agent, resp: dict) -> str | None:
        if self.nudges >= self.max_nudges:
            return None
        edited = verified = False
        for m in agent.messages:
            if m["role"] != "assistant":
                continue
            for c in m.get("tool_calls") or []:
                args = c.get("args") or {}
                if c["name"] in EDIT_TOOLS and str(args.get("path", "")).endswith(CODE_SUFFIXES):
                    edited, verified = True, False  # a new edit voids earlier checks
                elif c["name"] == "bash" and any(w in str(args.get("cmd", "")) for w in VERIFY_WORDS):
                    verified = True
        if edited and not verified:
            self.nudges += 1
            return "You changed code but have not run tests or a linter since. Run one, then answer."
        return None


def drain_inbox(agent: Agent) -> None:
    """Middleware. Anything the user typed mid-run joins the conversation before the next call."""
    while agent.inbox:
        agent.messages.append({"role": "user", "content": agent.inbox.pop(0)})
