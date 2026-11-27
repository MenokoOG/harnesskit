"""Module 1: a linear agent loop with hard limits, serial tools and surfaced errors."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .model import Model
from .schema import parameters_of


class LimitReached(Exception):
    """Raised by limits and middleware to end a run cleanly."""


def truncate(text: str, limit: int = 25_000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


@dataclass
class Agent:
    model: Model
    tools: dict[str, Callable[..., str]]
    system: str = "You are a coding agent."
    max_turns: int = 50
    max_cost: float = 5.0
    max_seconds: float = 600.0
    middleware: list[Callable[["Agent"], None]] = field(default_factory=list)  # module 2
    stop_guards: list[Callable[["Agent", dict], str | None]] = field(default_factory=list)  # module 2
    inbox: list[str] = field(default_factory=list)  # module 2: mid-run user input
    messages: list[dict] = field(default_factory=list)
    turns: int = 0
    cost: float = 0.0
    stop_reason: str = ""
    _started: float = field(default=0.0, init=False, repr=False)

    def schemas(self) -> list[dict]:
        """Rebuilt every turn, so tools added mid-run (module 3) show up."""
        return [
            {"name": n, "description": (f.__doc__ or n).strip(), "parameters": parameters_of(f)}
            for n, f in list(self.tools.items())
        ]

    def check_limits(self) -> None:
        if self.turns >= self.max_turns:
            raise LimitReached(f"max_turns={self.max_turns}")
        if self.cost >= self.max_cost:
            raise LimitReached(f"max_cost={self.max_cost}")
        if time.monotonic() - self._started >= self.max_seconds:
            raise LimitReached(f"max_seconds={self.max_seconds}")

    def veto(self, resp: dict) -> str | None:
        for guard in self.stop_guards:
            nudge = guard(self, resp)
            if nudge:
                return nudge
        return None

    def execute(self, call: dict) -> dict:
        name, args = call["name"], call.get("args") or {}
        tool = self.tools.get(name)
        if tool is None:
            out = f"ERROR: unknown tool {name!r}. Available: {', '.join(sorted(self.tools))}"
        else:
            try:
                out = str(tool(**args))
            except Exception as e:  # surfaced to the model, never swallowed
                out = f"ERROR: {type(e).__name__}: {e}"
        return {"role": "tool", "tool_call_id": call["id"], "name": name, "content": truncate(out)}

    def run(self, task: str) -> str:
        self.messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": task},
        ]
        self._started = time.monotonic()
        while True:
            try:
                self.check_limits()
                for mw in self.middleware:
                    mw(self)
            except LimitReached as e:
                self.stop_reason = str(e)
                return self.stop_reason
            resp = self.model.complete(self.messages, self.schemas())
            self.turns += 1
            self.cost += resp.get("cost", 0.0)
            self.messages.append(resp)
            calls = resp.get("tool_calls") or []
            if not calls:
                nudge = self.veto(resp)
                if nudge:
                    self.messages.append({"role": "user", "content": nudge})
                    continue
                self.stop_reason = "done"
                return resp.get("content", "")
            for call in calls:  # serial on purpose: the simplest safe choice
                result = self.execute(call)
                self.messages.append(result)
                for guard in self.stop_guards:  # guards see results before compaction can drop them
                    observe = getattr(guard, "observe", None)
                    if observe:
                        observe(call, result["content"])
