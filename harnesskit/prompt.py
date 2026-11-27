"""Module 7: a prompt with a static prefix and a dynamic tail, plus provider profiles."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def normalize_json(obj) -> str:
    """Sorted keys, no extra spaces. The same data always serializes to the same bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@dataclass
class PromptBuilder:
    static_sections: list[str]

    @property
    def static(self) -> str:
        return "\n\n".join(self.static_sections)

    def cache_key(self) -> str:
        return hashlib.blake2b(self.static.encode(), digest_size=8).hexdigest()

    def build(self, dynamic: dict[str, str]) -> tuple[str, str]:
        """Returns (prompt, cache key). Dynamic text always comes after the static prefix."""
        tail = "\n\n".join(f"<{k}>\n{v}\n</{k}>" for k, v in dynamic.items() if v)
        return (self.static + "\n\n" + tail).strip(), self.cache_key()


@dataclass(frozen=True)
class Profile:
    name: str
    cache: str  # "breakpoint", "key" or "none"


def system_payload(profile: Profile, static: str, dynamic: str, key: str):
    """Illustrative shapes only. Check each provider's current docs before you rely on a field name."""
    if profile.cache == "breakpoint":
        return [
            {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic},
        ]
    if profile.cache == "key":
        return {"system": static + "\n\n" + dynamic, "prompt_cache_key": key}
    return {"system": static + "\n\n" + dynamic}
