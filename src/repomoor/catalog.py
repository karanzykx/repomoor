"""Bundled informational tool catalog. Never installs or probes tools."""
from __future__ import annotations

import importlib.resources
import json
from typing import Any

def load_catalog() -> dict[str, Any]:
    """Bundled, informational catalog. Never installs or probes tools."""
    location = importlib.resources.files("repomoor").joinpath("data/tools.json")
    return json.loads(location.read_text(encoding="utf-8"))
