"""The hardline floor: commands that no rule and no mode can allow.

This is a speed bump, not a sandbox. `find / -delete` or a one-line script gets past it.
"""
from __future__ import annotations

import re
import shlex

PATTERNS = [
    re.compile(r"\brm\s+-\w*r\w*\s+(-\w+\s+)*/(?=[\s*\"';|&]|$)"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+.*of=/dev/"),
    re.compile(r":\(\)\s*\{"),
    re.compile(r"\bshutdown\b"),
]
ROOTS = {"/", "/*", "~", "~/", "~/*", "$HOME", "$HOME/", "$HOME/*", "${HOME}"}
SEPARATORS = set(";&|()")


def _segments(line: str) -> list[list[str]]:
    """Split one shell line into commands at ; & | and parentheses, honoring quotes."""
    lex = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    out: list[list[str]] = [[]]
    try:
        for token in lex:
            if set(token) <= SEPARATORS:
                out.append([])
            else:
                out[-1].append(token)
    except ValueError:  # unbalanced quotes: the patterns still apply, and the policy prompts
        return []
    return out


def _removes_a_root(argv: list[str]) -> bool:
    for i, token in enumerate(argv):
        if token.rsplit("/", 1)[-1] != "rm":
            continue
        rest = argv[i + 1 :]
        recursive = any(
            a == "--recursive" or (a.startswith("-") and not a.startswith("--") and ("r" in a or "R" in a))
            for a in rest
        )
        if recursive and any(a in ROOTS for a in rest):
            return True
    return False


def hits_floor(cmd: str) -> bool:
    if any(p.search(cmd) for p in PATTERNS):
        return True
    for line in cmd.splitlines():
        for argv in _segments(line):
            if _removes_a_root(argv):
                return True
            # `sh -c "..."` arrives as one quoted token, so look inside it.
            if any(" " in t and t != cmd and hits_floor(t) for t in argv):
                return True
    return False
