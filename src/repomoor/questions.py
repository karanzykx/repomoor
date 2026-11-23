"""Questionnaire: the question table, interactive prompts, and the strict --answers loader."""
from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Any

from .parsing import parse_json

def choose(question: str, options: list[tuple[str, str]], default: int, interactive: bool) -> str:
    if not interactive:
        return options[default][0]
    print("\n" + question)
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}. {label}{' [default]' if i == default + 1 else ''}")
    while True:
        try:
            reply = input(f"Choose [1-{len(options)}] (Enter={default+1}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled. No files changed.")
            raise SystemExit(130)
        if not reply:
            return options[default][0]
        if reply.isdigit() and 1 <= int(reply) <= len(options):
            return options[int(reply) - 1][0]
        print("Please enter one of the displayed numbers.")


QUESTIONS: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "agents": ("Which AI coding agents will you use?", [
        ("both", "Both Claude Code and Cursor"),
        ("claude", "Claude Code"),
        ("cursor", "Cursor"),
        ("other", "Other agents / undecided"),
    ]),
    "priority": ("What matters most for this project?", [
        ("balanced", "Balanced efficiency and correctness"),
        ("tokens", "Lowest total token usage / cost"),
        ("correctness", "Correct changes and dependency coverage"),
        ("speed", "Faster verified development"),
    ]),
    "pain": ("Where do you expect AI agents to waste the most effort?", [
        ("unknown", "Not sure yet"),
        ("rediscovery", "Repeated file exploration / forgotten decisions"),
        ("impact", "Missing callers, dependencies, or refactoring impact"),
        ("terminal", "Large CLI, test and build output"),
        ("browser", "Frontend/UI debugging in browsers"),
    ]),
    "future_project": ("A blank project: what are you planning?", [
        ("unknown", "Undecided / mixed"),
        ("web", "Web app (frontend + optional API)"),
        ("backend", "Backend / service"),
        ("multi", "Multi-service or monorepo"),
        ("library", "Library, CLI or small utility"),
    ]),
    "scope": ("Are these folders separate deployable services/packages?", [
        ("unsure", "Unsure; don't assume"),
        ("yes", "Yes, multiple services or packages"),
        ("no", "No, one application"),
    ]),
}
MAX_ANSWERS_BYTES = 16_384
ANSWERS_VERSION_KEY = "repomoor_answers_version"


class AnswersError(ValueError):
    """Answers file is unusable. Messages never echo file contents."""


def load_answers_file(path: Path) -> dict[str, str]:
    """Strictly read a small JSON answers file. Read-only; never executes anything.

    Accepts only known question keys with listed choice ids, plus an optional
    version marker. Error messages name keys/choices but never echo values.
    """
    try:
        st = os.stat(path)  # follows a symlink deliberately: the user named this file
    except OSError:
        raise AnswersError("answers file not found or not readable") from None
    if not stat.S_ISREG(st.st_mode):
        raise AnswersError("answers file must be a regular file")
    if st.st_size > MAX_ANSWERS_BYTES:
        raise AnswersError(f"answers file is larger than {MAX_ANSWERS_BYTES} bytes")
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_ANSWERS_BYTES + 1)
    except OSError:
        raise AnswersError("answers file not found or not readable") from None
    if len(raw) > MAX_ANSWERS_BYTES:
        raise AnswersError(f"answers file is larger than {MAX_ANSWERS_BYTES} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise AnswersError("answers file is not valid UTF-8 JSON") from None
    data, issue = parse_json(text)
    if issue == "too-deep":
        raise AnswersError("answers file is nested too deeply")
    if issue:
        raise AnswersError("answers file is not valid UTF-8 JSON")
    if not isinstance(data, dict):
        raise AnswersError("answers file must contain a JSON object")
    version = data.pop(ANSWERS_VERSION_KEY, 1)
    if version != 1 or isinstance(version, bool):
        raise AnswersError(f"unsupported {ANSWERS_VERSION_KEY}; expected 1")
    unknown = sorted(k for k in data if k not in QUESTIONS)
    if unknown:
        shown = ", ".join(repr(k[:40]) for k in unknown[:5])
        raise AnswersError(f"unknown answer key(s): {shown}; allowed: {', '.join(QUESTIONS)}")
    result: dict[str, str] = {}
    for key, value in data.items():
        allowed = [choice for choice, _ in QUESTIONS[key][1]]
        if not isinstance(value, str) or value not in allowed:
            raise AnswersError(f"invalid choice for {key!r}; allowed: {', '.join(allowed)}")
        result[key] = value
    return result


def answers_from_user(signals: dict[str, Any], scan: dict[str, Any], interactive: bool,
                      preset: dict[str, str] | None = None, quiet: bool = False) -> tuple[dict[str, str], dict[str, str]]:
    """Return (answers, sources). Sources: file, interactive, default, inferred, not-applicable."""
    preset = preset or {}
    if not quiet:
        print("\n=== RepoMoor ===")
        print("No installations. No global checks. Preview-only unless you pass --apply.")
        print("Detected: " + (", ".join(list(scan["source_counts"])[:5]) or "No source languages yet"))
        if signals["workspace_detected"] or signals["possible_multiservice"]:
            print("Detected: workspace/multiple project component signals")
        existing = signals["local_agent_configurations"]
        if existing:
            print("Existing local AI configurations: " + ", ".join(existing))
        nested = [x["path"] for x in signals.get("instruction_files", []) if x["scope"] == "nested"]
        if nested:
            print(f"Nested agent instructions: {len(nested)} (e.g. " + ", ".join(nested[:3]) + ")")
    answers: dict[str, str] = {}
    sources: dict[str, str] = {}

    def ask(key: str) -> None:
        if key in preset:
            answers[key], sources[key] = preset[key], "file"
            return
        question, options = QUESTIONS[key]
        answers[key] = choose(question, options, 0, interactive)
        sources[key] = "interactive" if interactive else "default"

    for key in ("agents", "priority", "pain"):
        ask(key)
    if signals["blank_or_uninitialized"]:
        ask("future_project")
    else:
        answers["future_project"], sources["future_project"] = "existing", "inferred"
    if signals["possible_multiservice"] and not signals["workspace_detected"]:
        ask("scope")
    else:
        answers["scope"] = "inferred" if signals["workspace_detected"] else "unsure"
        sources["scope"] = "inferred"
    for key in preset:
        if sources.get(key) != "file":
            sources[key] = "not-applicable"  # supplied, but the scan already decided this
    return answers, sources
