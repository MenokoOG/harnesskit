"""Build the parameter schema a real model needs from a tool's signature."""
from __future__ import annotations

import inspect
import typing
from typing import Callable

JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def parameters_of(tool: Callable) -> dict:
    target = inspect.unwrap(tool)  # hooks and the policy gate wrap tools
    hints = typing.get_type_hints(target)
    properties, required = {}, []
    for name, param in inspect.signature(target).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        properties[name] = {"type": JSON_TYPES.get(hints.get(name), "string")}
        if param.default is param.empty:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}
