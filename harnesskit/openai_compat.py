"""Adapter for an OpenAI-style /v1/chat/completions server, such as llama.cpp's llama-server.

One timeout, no retry. A transport or protocol failure raises and ends the run.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


def to_wire(message: dict) -> dict:
    if message["role"] == "tool":
        return {"role": "tool", "tool_call_id": message["tool_call_id"], "content": message["content"]}
    wire = {"role": message["role"], "content": message.get("content") or ""}
    if message.get("tool_calls"):
        wire["tool_calls"] = [
            {"id": c["id"], "type": "function",
             "function": {"name": c["name"], "arguments": json.dumps(c.get("args") or {})}}
            for c in message["tool_calls"]
        ]
    return wire


def parse_args(raw: str) -> dict:
    """Bad JSON from the model becomes a bad call, so the loop reports it back as an ERROR."""
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"invalid_json_arguments": raw}
    return args if isinstance(args, dict) else {"invalid_json_arguments": raw}


def from_wire(message: dict) -> dict:
    calls = [
        {"id": c["id"], "name": c["function"]["name"], "args": parse_args(c["function"].get("arguments", ""))}
        for c in message.get("tool_calls") or []
    ]
    return {"role": "assistant", "content": message.get("content") or "", "tool_calls": calls, "cost": 0.0}


@dataclass
class OpenAICompatModel:
    base_url: str
    model: str = "local"
    timeout: float = 600.0
    max_tokens: int = 768

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        body = {
            "model": self.model, "temperature": 0.2, "max_tokens": self.max_tokens,
            "messages": [to_wire(m) for m in messages],
            "tools": [{"type": "function", "function": t} for t in tools],
        }
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/v1/chat/completions",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.load(response)
        return from_wire(payload["choices"][0]["message"])
