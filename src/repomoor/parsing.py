"""Bounded parsing of untrusted text. No imports from other RepoMoor modules.

Results carry a short issue code instead of an exception message, so callers can
report what went wrong without echoing any of the input.
"""
from __future__ import annotations

import json
from typing import Any

MAX_JSON_DEPTH = 64


def json_depth_exceeds(text: str, limit: int = MAX_JSON_DEPTH) -> bool:
    """Linear scan for bracket nesting deeper than `limit`, ignoring brackets inside strings."""
    depth = 0
    in_string = escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                return True
        elif ch in "]}":
            depth -= 1
    return False


def parse_json(text: str) -> tuple[Any, str | None]:
    """Return (value, None) or (None, issue) with issue in {'too-deep', 'invalid-json'}."""
    if json_depth_exceeds(text):
        return None, "too-deep"
    try:
        return json.loads(text), None
    except (ValueError, RecursionError):
        return None, "invalid-json"
