"""Read-only project health checks (--doctor)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import OUTPUT_DIR
from .fs import read_bounded
from .parsing import parse_json

def check_project(root: Path, scan: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    """Non-mutating, strictly project-scoped advisory checks."""
    checks: list[dict[str, str]] = []

    def add(level: str, code: str, message: str) -> None:
        checks.append({"level": level, "code": code, "message": message})

    existing = list(signals["local_agent_configurations"])
    if existing:
        add("info", "existing-agent-configuration", "Found local AI configuration(s): " + ", ".join(existing) + ". No changes proposed.")
    nested = [x["path"] for x in signals.get("instruction_files", []) if x["scope"] == "nested"]
    if nested:
        add("info", "nested-instructions", f"Found {len(nested)} nested agent instruction location(s), e.g. " + ", ".join(nested[:5]) + ". --integrate will not add competing root rules.")
    if len(signals["configured_graph_tools"]) > 1:
        add("warn", "multiple-graph-candidates", "Multiple locally referenced graph/index tools found. Check overlap and agent usage before adding more.")
    if scan["scan_truncated"]:
        limits = ", ".join(scan.get("truncation_reasons") or ["max_files"])
        add("warn", "incomplete-scan", f"File scan was truncated ({limits}); recommendations are based on incomplete evidence.")
    if scan.get("dirs_unreadable"):
        add("warn", "unreadable-directories", f"{scan['dirs_unreadable']} director(ies) could not be read; their contents were not scanned.")
    if signals.get("parse_issues"):
        listed = ", ".join(f"{x['path']} ({x['code']})" for x in signals["parse_issues"])
        add("warn", "parse-issues", f"Some project files were skipped or could not be parsed: {listed}. Signals from them are missing.")
    if scan["symlinks_skipped"]:
        add("info", "symlinks-skipped", f"Skipped {scan['symlinks_skipped']} symlink(s) rather than following them.")
    if (root / OUTPUT_DIR).is_symlink():
        add("warn", "output-dir-symlink", "The output directory is a symlink. RepoMoor will not write through it.")
    prior, read_issue = read_bounded(root, f"{OUTPUT_DIR}/project-profile.json")
    if read_issue:
        add("warn", "profile-unreadable", f"Profile exists but cannot be read ({read_issue}). Existing file was left untouched.")
    elif prior is None:
        add("info", "no-saved-profile", "No readable generated profile found. Run with --apply to create one without overwriting files.")
    else:
        profile, parse_issue = parse_json(prior)
        try:
            if parse_issue:
                raise ValueError(parse_issue)
            old = profile["scan"]
            if old.get("manifests") != scan["manifests"] or old.get("source_counts") != scan["source_counts"]:
                add("warn", "profile-outdated", "Repository manifests or observed language counts changed since the saved profile. Current reports remain preserved; review and re-run on a fresh report location if needed.")
            else:
                add("ok", "profile-matches-scan", "Saved profile matches the current sampled manifests and language counts.")
        except (ValueError, TypeError, KeyError, AttributeError):
            add("warn", "profile-unreadable", "Profile exists but cannot be interpreted. Existing file was left untouched.")
    add("info", "runtime-not-checked", "No commands, MCP servers, global settings, or third-party installations were executed or tested.")
    return {"root": str(root), "checks": checks, "warning_count": sum(x["level"] == "warn" for x in checks)}
