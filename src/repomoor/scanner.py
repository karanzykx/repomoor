"""Read-only repository discovery: file names, bounded manifests, project-local config keywords.

Never executes project code, never reads global/user settings, never follows symlinks.
"""
from __future__ import annotations

import collections
import os
from pathlib import Path
import re
from typing import Any

from .constants import OUTPUT_DIR
from .fs import local_exists, read_bounded, safe_read
from .parsing import parse_json

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".next", ".nuxt", ".output",
    ".venv", "venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", ".turbo", "dist", "build", "target", "coverage",
    ".cache", "vendor", ".idea", ".gradle", "bin", "obj", OUTPUT_DIR,
    "graft", ".trail", ".gitnexus", ".pnpm-store", ".yarn", ".svelte-kit",
}
SOURCE_EXTS = {
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".py": "Python", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin", ".cs": "C#", ".rb": "Ruby",
    ".php": "PHP", ".swift": "Swift", ".dart": "Dart", ".cpp": "C++",
    ".cc": "C++", ".c": "C", ".h": "C/C++", ".vue": "Vue",
    ".svelte": "Svelte", ".ex": "Elixir", ".exs": "Elixir",
}
MANIFEST_NAMES = {
    "package.json", "pnpm-workspace.yaml", "turbo.json", "nx.json", "lerna.json",
    "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "uv.lock",
    "Cargo.toml", "go.mod", "go.work", "pom.xml", "build.gradle",
    "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "composer.json", "Gemfile", "pubspec.yaml", "Dockerfile", "docker-compose.yml",
    "docker-compose.yaml", "compose.yml", "compose.yaml", "Makefile",
}
AGENT_PATHS = {
    "AGENTS.md": "Shared/Cursor-style agent instructions",
    "CLAUDE.md": "Claude Code instructions",
    ".cursorrules": "Legacy Cursor instructions",
    ".cursor/rules": "Cursor project rules",
    ".cursor/mcp.json": "Cursor project MCP configuration",
    ".mcp.json": "Claude Code project MCP configuration",
    ".claude/rules": "Claude Code scoped rules",
    ".claude/skills": "Claude Code project skills",
    ".claude/settings.json": "Claude Code project settings/hooks",
    ".github/copilot-instructions.md": "Copilot project instructions",
    ".windsurf/rules": "Windsurf project rules",
    ".trail": "Trail-Code project data",
    "graft": "Trail/Graft local code map",
    ".rtk": "RTK project configuration",
    ".gitnexus": "GitNexus local project state",
    "repomix.config.json": "Repomix project configuration",
    "repomix.config.ts": "Repomix project configuration",
    # Further project-local instruction locations (P0-02). Never global/user paths.
    "CLAUDE.local.md": "Claude Code personal project instructions",
    ".claude/CLAUDE.md": "Claude Code instructions",
    ".claude/commands": "Claude Code project slash commands",
    ".claude/agents": "Claude Code project subagents",
    ".claude/settings.local.json": "Claude Code personal project settings",
    "GEMINI.md": "Gemini CLI instructions",
    ".github/instructions": "Copilot path-specific instructions",
    ".github/prompts": "Copilot prompt files",
    ".windsurfrules": "Legacy Windsurf instructions",
    ".clinerules": "Cline instructions",
    ".roo/rules": "Roo Code project rules",
    ".roorules": "Roo Code instructions",
    ".continue/rules": "Continue project rules",
    ".junie/guidelines.md": "JetBrains Junie guidelines",
    ".kiro/steering": "Kiro steering files",
    ".aider.conf.yml": "Aider project configuration",
}
# Entries in AGENT_PATHS that carry instructions an agent will follow. Their presence (at the
# root or nested) blocks --integrate, because a new root rule file could compete with them.
INSTRUCTION_PATHS = frozenset({
    "AGENTS.md", "CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md", ".cursorrules", ".cursor/rules",
    ".claude/rules", ".claude/skills", ".claude/commands", ".claude/agents", ".github/copilot-instructions.md",
    ".github/instructions", ".github/prompts", ".windsurf/rules", ".windsurfrules", ".clinerules", ".roo/rules",
    ".roorules", ".continue/rules", ".junie/guidelines.md", ".kiro/steering", "GEMINI.md",
})
# File names agents also honour in subdirectories, matched case-insensitively so detection
# does not depend on the filesystem. False positives only skip integration (the safe side).
NESTED_RULE_NAMES = frozenset({"agents.md", "claude.md", "claude.local.md", "gemini.md"})
MAX_NESTED_RULES = 200
EXISTING_GRAPH_KEYWORDS = ("trail", "graft", "gitnexus", "codebase-memory", "code-review-graph", "jcodemunch", "graphify", "toktoken", "tokensave", "codemap", "sprout")
OUTPUT_KEYWORDS = ("rtk", "headroom", "caveman")
REPO_CONFIG_PATHS = [".mcp.json", ".cursor/mcp.json", ".claude/settings.json"]


MAX_DIRS_DEFAULT = 6000
MAX_DIR_ENTRIES = 20_000  # per directory listing; bounds memory on pathological folders
MAX_PARSE_ISSUES = 20


def enumerate_repo(root: Path, max_files: int, max_depth: int, max_dirs: int = MAX_DIRS_DEFAULT) -> dict[str, Any]:
    counts: collections.Counter[str] = collections.Counter()
    manifests: list[str] = []
    component_roots: set[str] = set()
    files_examined = 0
    skipped_links = 0
    unreadable_dirs = 0
    reasons: set[str] = set()
    cut_off = False
    dirs_seen = 0
    queued = 1  # directories ever placed on the stack, root included; never exceeds max_dirs
    nested_rules: list[str] = []

    def note_rule(rel: str) -> None:
        if rel in AGENT_PATHS:
            return  # exact root-level locations are checked directly by project_signals
        if len(nested_rules) < MAX_NESTED_RULES:
            nested_rules.append(rel)
        else:
            reasons.add("max_nested_rules")
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        dirs_seen += 1
        listing = []
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if len(listing) == MAX_DIR_ENTRIES:
                        reasons.add("max_dir_entries")
                        break
                    listing.append(entry)
        except OSError:
            unreadable_dirs += 1
            continue
        listing.sort(key=lambda e: e.name)
        for entry in listing:
            try:
                if entry.is_symlink():
                    skipped_links += 1
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() == "rules" and os.path.basename(directory).lower() == ".cursor" and depth >= 1:
                        note_rule(Path(entry.path).relative_to(root).as_posix())
                    if depth < max_depth and entry.name not in SKIP_DIRS and not entry.name.startswith(".git"):
                        if queued >= max_dirs:
                            reasons.add("max_dirs")
                        else:
                            queued += 1
                            stack.append((Path(entry.path), depth + 1))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if entry.name.lower() in NESTED_RULE_NAMES:  # root case variants too, e.g. agents.md on Linux
                note_rule(Path(entry.path).relative_to(root).as_posix())
            files_examined += 1
            if files_examined > max_files:
                cut_off = True
                reasons.add("max_files")
                break
            file_path = Path(entry.path)
            suffix = file_path.suffix.lower()
            if suffix in SOURCE_EXTS:
                counts[SOURCE_EXTS[suffix]] += 1
            if entry.name in MANIFEST_NAMES:
                rel = file_path.relative_to(root).as_posix()
                manifests.append(rel)
                if depth >= 1:
                    component_roots.add(file_path.parent.relative_to(root).as_posix())
        if cut_off:
            break
    return {
        "source_counts": dict(counts.most_common()),
        "sampled_source_files": sum(counts.values()),
        "files_examined": min(files_examined, max_files),
        "scan_truncated": bool(reasons),
        "truncation_reasons": sorted(reasons),
        "dirs_examined": dirs_seen,
        "dirs_unreadable": unreadable_dirs,
        "symlinks_skipped": skipped_links,
        "manifests": sorted(manifests),
        "component_roots": sorted(component_roots),
        "nested_rule_paths": sorted(nested_rules),
    }


def contains_keyword_in_config(root: Path, word: str) -> bool:
    """Kept for v0.2 callers; project_signals reads each config once instead."""
    return any(body and _keyword_in(body, word) for body in (safe_read(root, p) for p in REPO_CONFIG_PATHS))


def _keyword_in(body: str, word: str) -> bool:
    return bool(re.search(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", body, re.I))


def project_signals(root: Path, scan: dict[str, Any]) -> dict[str, Any]:
    found = {k: v for k, v in AGENT_PATHS.items() if local_exists(root, k)}
    instruction_files = [{"path": p, "scope": "root", "description": AGENT_PATHS[p]} for p in found if p in INSTRUCTION_PATHS]
    # On case-insensitive filesystems a root `agents.md` already matched `AGENTS.md` above.
    known = {p.lower() for p in found}
    instruction_files += [
        {"path": p, "scope": "nested" if "/" in p else "root", "description": "Scoped agent instructions" if "/" in p else "Agent instructions (name case differs)"}
        for p in scan.get("nested_rule_paths", []) if p.lower() not in known
    ]
    issues: list[dict[str, str]] = []

    def read(rel: str) -> str | None:
        text, issue = read_bounded(root, rel)
        if issue and len(issues) < MAX_PARSE_ISSUES:
            issues.append({"path": rel, "code": issue})
        return text

    # Configuration parsing is deliberately not printed: MCP JSON may contain credentials.
    # Each config file is read once; only fixed keyword names are ever reported.
    config_bodies = [body for body in (read(p) for p in REPO_CONFIG_PATHS) if body]
    configured_graph = [k for k in EXISTING_GRAPH_KEYWORDS if any(_keyword_in(b, k) for b in config_bodies)]
    configured_output = [k for k in OUTPUT_KEYWORDS if any(_keyword_in(b, k) for b in config_bodies)]
    if any(local_exists(root, path) for path in [".trail", "graft"]):
        configured_graph.append("trail (project files)")
    if local_exists(root, ".gitnexus"):
        configured_graph.append("gitnexus (project files)")
    if local_exists(root, ".rtk"):
        configured_output.append("rtk (project files)")
    root_files = [Path(p).name for p in scan["manifests"] if "/" not in p]
    workspace_markers = {
        "pnpm-workspace.yaml", "turbo.json", "nx.json", "lerna.json", "go.work"
    }
    workspace_evidence = sorted(workspace_markers.intersection(root_files))
    cargo = read("Cargo.toml")
    # [ \t]* rather than \s*: \s can span newlines, which made this quadratic on blank lines.
    if cargo and re.search(r"(?m)^[ \t]*\[workspace\]", cargo):
        workspace_evidence.append("Cargo.toml [workspace]")
    package = read("package.json")
    deps: set[str] = set()
    if package:
        data, issue = parse_json(package)
        if issue:
            issues.append({"path": "package.json", "code": issue})
        elif not isinstance(data, dict):
            issues.append({"path": "package.json", "code": "not-object"})
        else:
            if data.get("workspaces"):
                workspace_evidence.append("package.json workspaces")
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                val = data.get(key, {})
                if isinstance(val, dict):
                    deps.update(val.keys())
    is_workspace = bool(workspace_evidence)
    dirs = {p.split("/")[0] for p in scan["component_roots"]}
    service_dirs = {"services", "apps", "packages", "microservices", "backend", "frontend"}
    possible_multi = len(scan["component_roots"]) >= 3 or is_workspace or len(dirs & service_dirs) >= 2
    test_hints = any("test" in p.lower() or "spec" in p.lower() for p in scan["manifests"])
    # Only infer front-end from concrete source / manifest evidence.
    frontend = ("TypeScript" in scan["source_counts"] or "JavaScript" in scan["source_counts"] or "Vue" in scan["source_counts"] or "Svelte" in scan["source_counts"]) and (
        bool(deps & {"react", "next", "vue", "svelte", "@angular/core", "vite", "nuxt", "astro"})
        or "Vue" in scan["source_counts"] or "Svelte" in scan["source_counts"]
    )
    # An empty/new project is distinct from a small repo.
    blank = scan["sampled_source_files"] == 0 and not any(p in root_files for p in ["package.json", "pyproject.toml", "Cargo.toml", "go.mod"])
    return {
        "local_agent_configurations": found,
        "instruction_files": instruction_files,
        "configured_graph_tools": sorted(set(configured_graph)),
        "configured_output_tools": sorted(set(configured_output)),
        "workspace_detected": bool(is_workspace),
        "workspace_evidence": workspace_evidence,
        "possible_multiservice": bool(possible_multi),
        "frontend_detected": bool(frontend),
        "test_hints_found": bool(test_hints),
        "blank_or_uninitialized": bool(blank),
        "parse_issues": issues,
    }
