"""Capstone: wire every subsystem into one agent."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .context import Compactor, discover_context
from .edit import edit
from .extend import Hooks, discover_skills, make_skill_tool, make_subagent_tool, skills_index
from .guards import StuckDetector, drain_inbox
from .loop import Agent
from .policy import DEFAULT_RULES, Policy, gated
from .prompt import PromptBuilder
from .tools import default_tools
from .verify import VerifyOnStop


def no_env_writes(name: str, args: dict) -> str | None:
    if name in ("write_file", "edit", "search_replace") and Path(str(args.get("path", ""))).name.startswith(".env"):
        return "writing .env files is not allowed"
    return None


def build_agent(model, *, root: Path, skills_dir: Path, bash: Callable | None = None,
                summarize: Callable[[str], str] | None = None, ask: Callable[[str], bool] | None = None,
                child_model: Callable | None = None, mode: str = "default") -> Agent:
    base = default_tools()
    tools = {k: v for k, v in base.items() if k != "bash"}
    tools["bash"] = gated(bash or base["bash"], Policy(DEFAULT_RULES), mode, ask or (lambda cmd: False))
    tools["edit"] = edit
    skills = discover_skills([skills_dir])
    tools["skill"] = make_skill_tool(skills)
    hooks = Hooks()
    hooks.on_pre(no_env_writes)
    tools = hooks.wrap(tools)
    if child_model:
        tools["task"] = make_subagent_tool(child_model, tools, {"read_file"})
    builder = PromptBuilder(["You are a coding agent. Read before you edit. Run a check before you finish."])
    system, _ = builder.build({"context": discover_context(root, root), "skills": skills_index(skills)})
    return Agent(
        model, tools, system=system,
        middleware=[drain_inbox, StuckDetector(warn_after=3, halt_after=6),
                    Compactor(summarize or (lambda p: "summary"), threshold_tokens=50_000)],
        stop_guards=[VerifyOnStop()],
    )
