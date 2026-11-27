"""Read and write text without changing a file's line endings."""
from __future__ import annotations

import pathlib


def read_exact(path: pathlib.Path) -> str:
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write_exact(path: pathlib.Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def to_newline(text: str, newline: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", newline)
