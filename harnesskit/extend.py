"""Module 6: skills, hooks and sub-agents."""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .loop import Agent


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    path: Path


def parse_skill(path: Path) -> Skill:
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"{path}: missing frontmatter")
    head, body = text[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    for need in ("name", "description"):
        if not meta.get(need):
            raise ValueError(f"{path}: frontmatter needs {need}")
    return Skill(meta["name"], meta["description"], body.strip(), Path(path))


def discover_skills(dirs: list[Path]) -> dict[str, Skill]:
    """dirs are in priority order. The first folder that defines a name keeps it."""
    found: dict[str, Skill] = {}
    for d in dirs:
        for p in sorted(Path(d).glob("*/SKILL.md")):
            s = parse_skill(p)
            found.setdefault(s.name, s)
    return found


def skills_index(skills: dict[str, Skill]) -> str:
    """Only names and descriptions go in the prompt. Bodies load on demand."""
    lines = [f"- {s.name}: {s.description}" for s in skills.values()]
    return "<available_skills>\n" + "\n".join(lines) + "\n</available_skills>"


def make_skill_tool(skills: dict[str, Skill]) -> Callable[[str], str]:
    def skill(name: str) -> str:
        """Load the full instructions of a skill by name."""
        s = skills.get(name)
        return s.body if s else f"ERROR: unknown skill {name!r}. Known: {', '.join(sorted(skills))}"

    return skill


class Hooks:
    """Pre hooks may block a call by returning a reason. Post hooks may rewrite the output."""

    def __init__(self):
        self.pre: list[Callable[[str, dict], str | None]] = []
        self.post: list[Callable[[str, dict, str], str | None]] = []

    def on_pre(self, fn):
        self.pre.append(fn)
        return fn

    def on_post(self, fn):
        self.post.append(fn)
        return fn

    def wrap(self, tools: dict[str, Callable]) -> dict[str, Callable]:
        def make(name: str, tool: Callable) -> Callable:
            @functools.wraps(tool)
            def run(**args):
                for fn in self.pre:
                    reason = fn(name, args)
                    if reason:
                        return f"BLOCKED by hook: {reason}"
                out = tool(**args)
                for fn in self.post:
                    out = fn(name, args, out) or out
                return out

            return run

        return {n: make(n, f) for n, f in tools.items()}


def make_subagent_tool(model_factory: Callable, parent_tools: dict, allowed: set[str], max_turns: int = 20):
    """The child gets a fresh context and only the allowed tools. The parent sees one string back."""

    def task(prompt: str) -> str:
        """Run a focused sub-task in a fresh context and return only its final answer."""
        child_tools = {n: f for n, f in parent_tools.items() if n in allowed}
        return Agent(model_factory(), child_tools, max_turns=max_turns).run(prompt)

    return task
