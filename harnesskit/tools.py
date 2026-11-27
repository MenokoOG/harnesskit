"""Module 1: the four starter tools. Every tool takes plain arguments and returns a string."""
from __future__ import annotations

import pathlib
import subprocess

from .textio import newline_of, read_exact, to_newline, write_exact


def bash(cmd: str, timeout: int = 120) -> str:
    """Run a shell command and return its exit code, stdout and stderr."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return f"exit={r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"


def read_file(path: str, offset: int = 0, limit: int = 2000) -> str:
    """Read a text file. Lines are numbered. Use offset and limit for big files."""
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    chunk = lines[offset : offset + limit]
    return "\n".join(f"{i + 1:4}: {line}" for i, line in enumerate(chunk, start=offset))


def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with the given content."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} characters to {path}"


def search_replace(path: str, search: str, replace: str) -> str:
    """Replace one exact occurrence of search with replace. Fails if it is missing or not unique."""
    p = pathlib.Path(path)
    text = read_exact(p)
    nl = newline_of(text)
    search, replace = to_newline(search, nl), to_newline(replace, nl)
    n = text.count(search)
    if n != 1:
        return f"ERROR: search string occurs {n} times, it must occur exactly once"
    write_exact(p, text.replace(search, replace, 1))
    return "OK"


def default_tools() -> dict:
    return {f.__name__: f for f in (bash, read_file, write_file, search_replace)}
