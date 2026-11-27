"""Verify-on-stop: a final answer after a code edit needs a check that ran and passed."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .loop import Agent

EDIT_TOOLS = {"write_file", "search_replace", "edit"}
CODE_SUFFIXES = (".py", ".ts", ".js", ".rs", ".go", ".java")
VERIFIER = re.compile(r"^(python3? -m (pytest|unittest)|pytest|npm test|cargo test|go test|ruff|mypy|tsc)(\s|$)")


def is_verifier(cmd: str) -> bool:
    """The command must run a checker. Pipes, ; and newlines can hide a failure, so they don't count."""
    if re.search(r"[;|\n\r]", cmd):
        return False
    return any(VERIFIER.match(part.strip()) for part in cmd.split("&&"))


@dataclass
class VerifyOnStop:
    """Stop guard. State is kept per call id, so compaction can't erase an unverified edit."""

    max_nudges: int = 2
    nudges: int = 0
    unverified: bool = False

    def observe(self, call: dict, result: str) -> None:
        args = call.get("args") or {}
        if call["name"] in EDIT_TOOLS and str(args.get("path", "")).endswith(CODE_SUFFIXES):
            if result.startswith(("OK", "wrote")):  # a blocked or failed edit changed nothing
                self.unverified = True
        elif call["name"] == "bash" and is_verifier(str(args.get("cmd", ""))):
            if result.startswith("exit=0"):  # a failing check proves nothing
                self.unverified = False

    def __call__(self, agent: Agent, resp: dict) -> str | None:
        if self.nudges >= self.max_nudges or not self.unverified:
            return None
        self.nudges += 1
        return "You changed code and no test or linter has passed since. Run one, then answer."
