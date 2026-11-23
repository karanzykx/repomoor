"""Golden-output tests: every user-visible output for a fixed set of fixture repos.

Any change to preview text, JSON, doctor checks, error messages or written report
files shows up here as a diff. When a change is intended, regenerate and review:

    REPOMOOR_UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden
    # then review the diff of tests/golden/ before committing it

Fixtures are built in temporary directories from the descriptions below, so no
symlinks, FIFOs or permission tricks are checked in. Temporary paths are replaced
with <ROOT> / <ANSWERS> so the files are stable across machines.
"""
from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
SCRIPT = BASE / "repomoor.py"
GOLDEN = Path(__file__).resolve().parent / "golden"
UPDATE = os.environ.get("REPOMOOR_UPDATE_GOLDEN") == "1"

FIXTURES: dict[str, dict[str, str]] = {
    "blank": {},
    "small-python": {"main.py": "print('hi')\n", "pyproject.toml": "[project]\nname = 'small'\n"},
    "mid-python": {**{f"pkg/m{i:02}.py": "pass\n" for i in range(85)}, "pyproject.toml": "[project]\nname = 'mid'\n"},
    "pnpm-monorepo": {
        "pnpm-workspace.yaml": "packages: ['apps/*']\n",
        "package.json": json.dumps({"name": "root", "private": True, "workspaces": ["apps/*"]}),
        "apps/web/package.json": json.dumps({"name": "web", "dependencies": {"react": "^18"}}),
        "apps/web/index.tsx": "export const App = () => null\n",
        "apps/api/package.json": json.dumps({"name": "api"}),
        "apps/api/server.ts": "export {}\n",
        "apps/worker/package.json": json.dumps({"name": "worker"}),
        "apps/worker/job.ts": "export {}\n",
    },
    "cargo-workspace": {"Cargo.toml": "[workspace]\nmembers = ['a']\n", "a/Cargo.toml": "[package]\nname = 'a'\n", "a/src/lib.rs": "\n"},
    "existing-graph-and-rules": {
        "main.py": "pass\n",
        ".mcp.json": json.dumps({"mcpServers": {"trail": {"command": "trail", "env": {"TOKEN": "SECRET-NEVER-ECHO"}}}}),
        "AGENTS.md": "# Team rules\n",
    },
    "existing-output-tool": {"main.py": "pass\n", ".rtk/config.toml": "\n"},
    "nested-rules": {
        "pnpm-workspace.yaml": "packages: ['apps/*']\n",
        "apps/web/AGENTS.md": "# Web rules\n",
        "apps/web/.cursor/rules/ui.mdc": "---\nglobs: '*.tsx'\n---\nUse the design system.\n",
        "apps/web/page.tsx": "export {}\n",
        "packages/core/claude.md": "lowercase name\n",
        "packages/core/index.ts": "export {}\n",
        "node_modules/dep/AGENTS.md": "vendored; must not count\n",
    },
    "broken-manifests": {"package.json": "[" * 500, "Cargo.toml": "\n" * 2000, "index.js": "\n"},
}
ANSWERS = {"agents": "claude", "priority": "correctness", "pain": "impact"}
# (name, extra args). "{answers}" is replaced with the answers file path.
RUNS: list[tuple[str, list[str]]] = [
    ("preview-text", ["--non-interactive"]),
    ("preview-json", ["--json"]),
    ("answers-json", ["--answers", "{answers}", "--json"]),
    ("small-dir-budget-json", ["--max-dirs", "2", "--json"]),
    ("doctor-before", ["--doctor", "--json"]),
    ("apply-integrate", ["--apply", "--integrate", "--answers", "{answers}", "--json"]),
    ("apply-again-text", ["--apply", "--non-interactive"]),
    ("doctor-after-text", ["--doctor"]),
]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "COLUMNS": "100", "NO_COLOR": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=60, env=env, encoding="utf-8")


def _normalise(text: str, replacements: dict[str, str]) -> str:
    for real, token in replacements.items():
        # JSON output escapes backslashes, so Windows paths also appear in doubled form.
        text = text.replace(json.dumps(real)[1:-1], token).replace(real, token)
    return text


def _record(result: subprocess.CompletedProcess[str], replacements: dict[str, str]) -> dict:
    out = _normalise(result.stdout, replacements)
    try:
        stdout: object = json.loads(out)
    except ValueError:
        stdout = out.splitlines()
    # argparse usage lines wrap differently across Python versions; keep only the error line.
    err = [line for line in _normalise(result.stderr, replacements).splitlines() if "error:" in line or "Traceback" in line]
    return {"returncode": result.returncode, "stdout": stdout, "stderr": err}


def capture_fixture(name: str) -> dict:
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
        root = Path(d).resolve() / name
        root.mkdir()
        for rel, body in FIXTURES[name].items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        answers = Path(a).resolve() / "answers.json"
        answers.write_text(json.dumps(ANSWERS), encoding="utf-8")
        replacements = {str(answers): "<ANSWERS>", str(root): "<ROOT>"}
        record: dict = {"runs": {}}
        for run_name, extra in RUNS:
            args = [str(root)] + [str(answers) if x == "{answers}" else x for x in extra]
            record["runs"][run_name] = _record(_run(args), replacements)
        record["files_after_apply"] = {
            p.relative_to(root).as_posix(): _normalise(p.read_text(encoding="utf-8"), replacements).splitlines()
            for p in sorted(root.rglob("*")) if p.is_file() and p.relative_to(root).as_posix() not in FIXTURES[name]
        }
        return record


def capture_commands() -> dict:
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
        root = Path(d).resolve()
        bad = Path(a).resolve() / "bad.json"
        replacements = {str(bad): "<ANSWERS>", str(root): "<ROOT>"}
        cases = {
            "catalog-text": ["--catalog"],
            "version": ["--version"],
            "integrate-without-apply": [str(root), "--integrate"],
            "doctor-with-apply": [str(root), "--doctor", "--apply"],
            "catalog-with-apply": ["--catalog", "--apply"],
            "max-dirs-out-of-range": [str(root), "--max-dirs", "0"],
            "missing-root": [str(root / "missing")],
        }
        record = {name: _record(_run(args), replacements) for name, args in cases.items()}
        for label, body in (("answers-unknown-key", '{"agent": "claude"}'), ("answers-bad-choice", '{"agents": "sk-SECRET"}'),
                            ("answers-too-deep", "[" * 1000), ("answers-not-json", "{nope")):
            bad.write_text(body, encoding="utf-8")
            record[label] = _record(_run([str(root), "--answers", str(bad), "--json"]), replacements)
        return record


class GoldenOutputTests(unittest.TestCase):
    maxDiff = None

    def _check(self, golden_name: str, actual: dict) -> None:
        path = GOLDEN / f"{golden_name}.json"
        rendered = json.dumps(actual, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
        if UPDATE:
            GOLDEN.mkdir(exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
            return
        self.assertTrue(path.is_file(), f"missing {path.name}; run with REPOMOOR_UPDATE_GOLDEN=1 and review it")
        expected = path.read_text(encoding="utf-8")
        if expected != rendered:
            diff = list(difflib.unified_diff(expected.splitlines(), rendered.splitlines(), f"golden/{path.name}", "actual", lineterm="", n=2))
            shown = "\n".join(diff[:80]) + (f"\n... {len(diff) - 80} more diff lines" if len(diff) > 80 else "")
            self.fail(f"Output changed for {golden_name}. If intended, regenerate with REPOMOOR_UPDATE_GOLDEN=1 and review.\n{shown}")

    def test_fixture_outputs(self):
        for name in FIXTURES:
            with self.subTest(fixture=name):
                self._check(name, capture_fixture(name))

    def test_command_outputs(self):
        self._check("commands", capture_commands())

    def test_no_stale_golden_files(self):
        expected = {f"{n}.json" for n in FIXTURES} | {"commands.json"}
        present = {p.name for p in GOLDEN.glob("*.json")} if GOLDEN.is_dir() else set()
        self.assertEqual(present - expected, set(), "golden files without a fixture; delete them")

    def test_golden_files_hold_no_secrets(self):
        for path in GOLDEN.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("SECRET-NEVER-ECHO", text, path.name)
            self.assertNotIn("sk-SECRET", text, path.name)


if __name__ == "__main__":
    unittest.main()
