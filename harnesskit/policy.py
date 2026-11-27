"""Module 5: command policy as data, a hardline floor that survives yolo, and three modes."""
from __future__ import annotations

import functools
import re
import shlex
from dataclasses import dataclass
from typing import Callable

from .floor import hits_floor

ALLOW, PROMPT, FORBIDDEN = "allow", "prompt", "forbidden"
ORDER = [ALLOW, PROMPT, FORBIDDEN]

@dataclass(frozen=True)
class Rule:
    pattern: tuple
    decision: str
    match: tuple = ()      # example commands that must hit this rule
    not_match: tuple = ()  # example commands that must not

    def applies(self, argv) -> bool:
        return tuple(argv[: len(self.pattern)]) == self.pattern


class Policy:
    def __init__(self, rules: list[Rule]):
        for r in rules:  # inline examples are tests, checked when the policy loads
            for ex in r.match:
                if not r.applies(ex):
                    raise ValueError(f"rule {r.pattern} should match {ex}")
            for ex in r.not_match:
                if r.applies(ex):
                    raise ValueError(f"rule {r.pattern} should not match {ex}")
        self.rules = rules

    def decide(self, cmd: str, mode: str = "default") -> str:
        if hits_floor(cmd):
            return FORBIDDEN
        compound = bool(re.search(r"[;&|`$<>\n\r]", cmd))  # newlines chain commands too
        try:
            argv = shlex.split(cmd)
        except ValueError:
            argv = []
        verdict = PROMPT
        if argv and not compound:
            hits = [r.decision for r in self.rules if r.applies(argv)]
            if hits:
                verdict = max(hits, key=ORDER.index)  # the strictest matching rule wins
        if verdict == FORBIDDEN:
            return FORBIDDEN
        if mode == "plan":
            return ALLOW if verdict == ALLOW else FORBIDDEN
        if mode == "yolo" and verdict == PROMPT:
            return ALLOW
        return verdict


DEFAULT_RULES = [
    Rule(("git", "status"), ALLOW, match=(("git", "status"), ("git", "status", "--short")), not_match=(("git", "push"),)),
    Rule(("git", "push"), PROMPT),
    Rule(("ls",), ALLOW),
    Rule(("cat",), ALLOW),
    Rule(("echo",), ALLOW),
]


def gated(tool: Callable, policy: Policy, mode: str, ask: Callable[[str], bool]) -> Callable:
    """Wrap a bash-like tool so every command passes through the policy first."""

    @functools.wraps(tool)
    def run(cmd: str, **kw):
        d = policy.decide(cmd, mode)
        if d == FORBIDDEN:
            return f"BLOCKED: policy forbids this command ({mode} mode)"
        if d == PROMPT and not ask(cmd):
            return "DENIED: the user declined this command"
        return tool(cmd, **kw)

    return run
