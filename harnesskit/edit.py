"""Module 3: an exact, unique edit contract with a small drift-tolerant fallback."""
from __future__ import annotations

import pathlib
import unicodedata

QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}


def canon(line: str) -> str:
    """Normalize a line for comparison only: NFKC, straight quotes, no trailing space."""
    line = unicodedata.normalize("NFKC", line)
    for fancy, plain in QUOTES.items():
        line = line.replace(fancy, plain)
    return line.rstrip()


def edit(path: str, old: str, new: str) -> str:
    """Replace one occurrence of old with new. old must match exactly once, so include enough lines."""
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    if n == 1:
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return "OK"
    if n > 1:
        return f"ERROR: old string occurs {n} times. Add surrounding lines to make it unique."
    # Fallback: compare whole lines after normalization, and replace whole lines.
    lines = text.split("\n")
    want = [canon(x) for x in old.split("\n")]
    have = [canon(x) for x in lines]
    hits = [i for i in range(len(lines) - len(want) + 1) if have[i : i + len(want)] == want]
    if len(hits) != 1:
        return "ERROR: old string not found" if not hits else "ERROR: old string is ambiguous after normalization"
    i = hits[0]
    lines[i : i + len(want)] = new.split("\n")
    p.write_text("\n".join(lines), encoding="utf-8")
    return "OK (matched after quote and whitespace normalization)"
