"""Offline regression tests. No user configuration or network is accessed."""
from __future__ import annotations

import ast
import errno
import os
import threading
import time
from unittest import mock
import itertools
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from repomoor import cli, fs, parsing, scanner

SCRIPT = BASE / "repomoor.py"
DEFAULTS = {"agents": "both", "priority": "balanced", "pain": "unknown", "future_project": "unknown", "scope": "unsure"}


def run_cli(root: Path | None = None, *options: str) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(SCRIPT)]
    if root is not None:
        argv.append(str(root))
    argv.extend(options)
    return subprocess.run(argv, capture_output=True, text=True, timeout=15)


class DiscoveryTests(unittest.TestCase):
    def test_blank_repository_does_not_get_code_graph(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            scan = cli.enumerate_repo(root, 1000, 6)
            signals = cli.project_signals(root, scan)
            self.assertTrue(signals["blank_or_uninitialized"])
            plan = cli.make_recommendations(scan, signals, DEFAULTS)
            self.assertEqual(len(plan["recommended"]), 1)
            self.assertNotIn("Trail-Code", str(plan["recommended"]))

    def test_monorepo_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "pnpm-workspace.yaml").write_text("packages: ['apps/*']\n")
            (root / "apps" / "api").mkdir(parents=True)
            (root / "apps" / "api" / "package.json").write_text('{"name":"api"}')
            (root / "apps" / "api" / "app.ts").write_text("export const a = 1")
            scan = cli.enumerate_repo(root, 1000, 6)
            self.assertEqual(scan["source_counts"]["TypeScript"], 1)
            self.assertTrue(cli.project_signals(root, scan)["workspace_detected"])

    def test_symlinked_directory_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            root = Path(d).resolve()
            (Path(outside) / "secret.py").write_text("secret")
            try:
                (root / "external").symlink_to(Path(outside), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            scan = cli.enumerate_repo(root, 1000, 6)
            self.assertEqual(scan["sampled_source_files"], 0)
            self.assertGreater(scan["symlinks_skipped"], 0)
            self.assertIsNone(cli.safe_read(root, "external/secret.py"))

    def test_manifest_content_not_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "package.json").write_text('{"scripts":{"postinstall":"touch SHOULD_NOT_EXIST"}}')
            self.assertEqual(run_cli(root, "--json").returncode, 0)
            self.assertFalse((root / "SHOULD_NOT_EXIST").exists())

    def test_config_secrets_not_echoed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / ".mcp.json").write_text(json.dumps({"mcpServers":{"trail":{"command":"trail", "env":{"TOKEN":"SECRET-NEVER-ECHO"}}}}))
            result = run_cli(root, "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SECRET-NEVER-ECHO", result.stdout)
            self.assertIn("trail", json.loads(result.stdout)["signals"]["configured_graph_tools"])

    def test_scan_truncation_visible(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for i in range(110):
                (root / f"a{i:03}.py").write_text("x=1\n")
            scan = cli.enumerate_repo(root, 100, 6)
            self.assertTrue(scan["scan_truncated"])
            self.assertLessEqual(scan["files_examined"], 100)


class FileSafetyTests(unittest.TestCase):
    def test_existing_instructions_are_never_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "CLAUDE.md").write_text("original instructions\n")
            result = run_cli(root, "--apply", "--integrate", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "CLAUDE.md").read_text(), "original instructions\n")
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertTrue((root / ".repomoor" / "recommendations.md").exists())

    def test_both_agents_one_shared_instructions_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            result = run_cli(root, "--apply", "--integrate", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "AGENTS.md").exists())
            self.assertFalse((root / "CLAUDE.md").exists())
            self.assertIn("PROJECT_CONTEXT.md", (root / "AGENTS.md").read_text())

    def test_create_only_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            self.assertEqual(cli.safe_create(root, ".repomoor/a.txt", "original"), "CREATED")
            self.assertIn("UNCHANGED", cli.safe_create(root, ".repomoor/a.txt", "original"))
            self.assertIn("PRESERVED", cli.safe_create(root, ".repomoor/a.txt", "replacement"))
            self.assertEqual((root / ".repomoor/a.txt").read_text(), "original")

    def test_symlinked_report_directory_rejected(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            root = Path(d).resolve()
            try:
                (root / ".repomoor").symlink_to(Path(outside), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            self.assertTrue(cli.safe_create(root, ".repomoor/profile.json", "x").startswith("REFUSED"))
            self.assertFalse((Path(outside) / "profile.json").exists())

    def test_no_files_written_in_preview(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            before = list(root.iterdir())
            self.assertEqual(run_cli(root, "--json").returncode, 0)
            self.assertEqual(before, list(root.iterdir()))

    def test_existing_agent_rules_elsewhere_skip_integration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / ".cursor" / "rules").mkdir(parents=True)
            (root / ".cursor" / "rules" / "mine.mdc").write_text("---\nalwaysApply: true\n---\nexisting\n")
            result = run_cli(root, "--apply", "--integrate", "--json")
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("AGENTS.md", json.loads(result.stdout)["apply_results"])

    def test_existing_generated_report_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            first = run_cli(root, "--apply", "--json")
            self.assertEqual(first.returncode, 0)
            original = (root / ".repomoor" / "project-profile.json").read_bytes()
            (root / "hello.py").write_text("hello = 'world'\n")
            second = run_cli(root, "--apply", "--json")
            self.assertEqual(second.returncode, 0)
            self.assertIn("PRESERVED", json.loads(second.stdout)["apply_results"][".repomoor/project-profile.json"])
            self.assertEqual((root / ".repomoor" / "project-profile.json").read_bytes(), original)


class CommandTests(unittest.TestCase):
    def test_catalog_has_all_nineteen(self):
        result = run_cli(None, "--catalog", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        items = json.loads(result.stdout)["tools"]
        self.assertEqual(len(items), 19)
        self.assertEqual(len({x["repository"] for x in items}), 19)
        self.assertTrue(all(x["installed_by_repomoor"] is False for x in items))

    def test_doctor_read_only_and_profile_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            before = run_cli(root, "--doctor", "--json")
            self.assertEqual(before.returncode, 0)
            self.assertIn("no-saved-profile", [x["code"] for x in json.loads(before.stdout)["checks"]])
            self.assertEqual(run_cli(root, "--apply", "--json").returncode, 0)
            current = run_cli(root, "--doctor", "--json")
            self.assertIn("profile-matches-scan", [x["code"] for x in json.loads(current.stdout)["checks"]])
            (root / "main.py").write_text("pass\n")
            changed = run_cli(root, "--doctor", "--json")
            self.assertIn("profile-outdated", [x["code"] for x in json.loads(changed.stdout)["checks"]])

    def test_invalid_cli_combinations_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            self.assertNotEqual(run_cli(root, "--integrate").returncode, 0)
            self.assertNotEqual(run_cli(root, "--doctor", "--apply").returncode, 0)
            self.assertNotEqual(run_cli(None, "--catalog", "--apply").returncode, 0)

    def test_module_and_entrypoint_cli_equivalent(self):
        env = None
        direct = run_cli(None, "--version")
        self.assertEqual(direct.returncode, 0)
        modular = subprocess.run([sys.executable, "-m", "repomoor", "--version"], cwd=BASE / "src", capture_output=True, text=True, timeout=15, env=env)
        self.assertEqual(modular.returncode, 0, modular.stderr)
        self.assertEqual(direct.stdout, modular.stdout)


class AnswersFileTests(unittest.TestCase):
    """--answers: strict, read-only, and refused before any write."""

    def _write(self, folder: str, payload: str) -> Path:
        path = Path(folder) / "answers.json"
        path.write_text(payload, encoding="utf-8")
        return path

    def test_valid_answers_are_used_and_traced(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
            root = Path(d).resolve()
            path = self._write(a, json.dumps({"repomoor_answers_version": 1, "agents": "claude", "pain": "terminal", "future_project": "library"}))
            result = run_cli(root, "--answers", str(path), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["answers"]["agents"], "claude")
            self.assertEqual(report["answers"]["pain"], "terminal")
            self.assertEqual(report["answers"]["future_project"], "library")
            self.assertEqual(report["answers"]["priority"], "balanced")
            self.assertEqual(report["answer_sources"]["agents"], "file")
            self.assertEqual(report["answer_sources"]["priority"], "default")
            self.assertEqual(report["answer_sources"]["scope"], "inferred")
            self.assertEqual(list(root.iterdir()), [])

    def test_inapplicable_answer_is_marked_not_used(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
            root = Path(d).resolve()
            (root / "main.py").write_text("pass\n")
            path = self._write(a, json.dumps({"future_project": "web"}))
            report = json.loads(run_cli(root, "--answers", str(path), "--json").stdout)
            self.assertEqual(report["answers"]["future_project"], "existing")
            self.assertEqual(report["answer_sources"]["future_project"], "not-applicable")

    def test_unknown_key_or_choice_rejected_without_echo(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
            root = Path(d).resolve()
            for payload in ({"agents": "sk-SECRETVALUE"}, {"agent": "claude"}, {"agents": ["claude"]},
                            {"repomoor_answers_version": 2}, ["claude"]):
                path = self._write(a, json.dumps(payload))
                result = run_cli(root, "--answers", str(path), "--json")
                self.assertEqual(result.returncode, 2, payload)
                self.assertNotIn("SECRETVALUE", result.stderr + result.stdout)
                self.assertEqual(result.stdout, "")

    def test_invalid_file_causes_no_writes_even_with_apply(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
            root = Path(d).resolve()
            cases = [self._write(a, "{not json"), Path(a) / "missing.json", Path(a)]
            big = Path(a) / "big.json"
            big.write_text(json.dumps({"agents": "claude", "pad": "x" * 20000}))
            cases.append(big)
            for path in cases:
                result = run_cli(root, "--answers", str(path), "--apply", "--integrate")
                self.assertEqual(result.returncode, 2, str(path))
                self.assertIn("No files changed", result.stderr)
                self.assertEqual(list(root.iterdir()), [])

    def test_answers_refused_with_doctor(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
            path = self._write(a, "{}")
            self.assertEqual(run_cli(Path(d), "--doctor", "--answers", str(path)).returncode, 2)

    def test_question_table_matches_recommender_values(self):
        for key, (_, options) in cli.QUESTIONS.items():
            self.assertEqual(options[0][0], DEFAULTS[key], key)


    def test_integrated_rules_link_an_existing_context_file(self):
        for agents, rule in (("claude", "CLAUDE.md"), ("both", "AGENTS.md")):
            with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
                root = Path(d).resolve()
                answers = Path(a) / "answers.json"
                answers.write_text(json.dumps({"agents": agents}))
                result = run_cli(root, "--apply", "--integrate", "--answers", str(answers), "--json")
                self.assertEqual(result.returncode, 0, result.stderr)
                links = re.findall(r"`([^`]+PROJECT_CONTEXT\.md)`", (root / rule).read_text())
                self.assertEqual(links, [".repomoor/PROJECT_CONTEXT.md"])
                self.assertTrue((root / links[0]).is_file())
                self.assertNotIn("ai-bootstrap", result.stdout + run_cli(root, "--help").stdout)


class ExplainableScoringTests(unittest.TestCase):
    """P1-04: every decision carries a registered reason code and its evidence."""

    OUTCOME_LISTS = {"recommended": "recommended", "optional_pilots": "optional", "skipped_details": "skipped"}

    @staticmethod
    def _fixtures(base: Path) -> dict[str, Path]:
        def make(name: str) -> Path:
            root = base / name
            root.mkdir()
            return root
        make("blank")
        small = make("small")
        (small / "main.py").write_text("pass\n")
        mid = make("mid")
        for i in range(85):
            (mid / f"m{i}.py").write_text("pass\n")
        ws = make("workspace")
        (ws / "pnpm-workspace.yaml").write_text("packages: ['apps/*']\n")
        (ws / "app.ts").write_text("export const a = 1\n")
        graph = make("graph")
        (graph / "main.py").write_text("pass\n")
        (graph / ".mcp.json").write_text(json.dumps({"mcpServers": {"trail": {"command": "trail", "env": {"TOKEN": "SECRET-NEVER-ECHO"}}}}))
        output = make("output")
        (output / "main.py").write_text("pass\n")
        (output / ".rtk").mkdir()
        return {p.name: p for p in base.iterdir()}

    def _matrix(self):
        with tempfile.TemporaryDirectory() as d:
            for name, root in self._fixtures(Path(d).resolve()).items():
                scan = cli.enumerate_repo(root, 1000, 6)
                signals = cli.project_signals(root, scan)
                keys = list(cli.QUESTIONS)
                for combo in itertools.product(*[[c for c, _ in cli.QUESTIONS[k][1]] for k in keys]):
                    answers = dict(zip(keys, combo))
                    yield name, signals, cli.make_recommendations(scan, signals, answers)

    def test_codes_registered_with_evidence_and_all_reachable(self):
        seen: set[str] = set()
        for name, _, plan in self._matrix():
            for field, outcome in self.OUTCOME_LISTS.items():
                for item in plan[field]:
                    self.assertIn(item["code"], cli.REASON_CODES, name)
                    self.assertEqual(cli.REASON_CODES[item["code"]][0], outcome, (name, item["code"]))
                    self.assertTrue(item["evidence"] and all(isinstance(e, str) and e for e in item["evidence"]), (name, item))
                    self.assertNotIn("SECRET-NEVER-ECHO", json.dumps(item))
                    seen.add(item["code"])
            self.assertEqual(plan["deliberately_skipped"], [x["reason"] for x in plan["skipped_details"]])
            self.assertEqual(plan["complexity_assessment"] == "potentially-complex", bool(plan["complexity_evidence"]))
        self.assertEqual(seen, set(cli.REASON_CODES), "unreachable or missing reason codes")

    def test_evidence_names_the_trigger(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures = self._fixtures(Path(d).resolve())
            def plan_for(name: str, **answers: str):
                root = fixtures[name]
                scan = cli.enumerate_repo(root, 1000, 6)
                signals = cli.project_signals(root, scan)
                return signals, cli.make_recommendations(scan, signals, {**DEFAULTS, "future_project": "existing", **answers})
            signals, plan = plan_for("workspace", pain="impact")
            self.assertEqual(signals["workspace_evidence"], ["pnpm-workspace.yaml"])
            pilot = next(x for x in plan["recommended"] if x["code"] == "GRAPH_PILOT_IMPACT")
            self.assertIn("signal:workspace_detected=pnpm-workspace.yaml", pilot["evidence"])
            self.assertIn("answer:pain=impact", pilot["evidence"])
            _, plan = plan_for("graph")
            self.assertIn("GRAPH_REUSE_EXISTING", [x["code"] for x in plan["recommended"]])
            self.assertIn("GRAPH_SKIP_DUPLICATE", [x["code"] for x in plan["skipped_details"]])
            _, plan = plan_for("small", pain="terminal")
            rtk = next(x for x in plan["optional_pilots"] if x["code"] == "OUTPUT_PILOT_TERMINAL")
            self.assertEqual(rtk["evidence"], ["answer:pain=terminal"])

    def test_codes_reach_json_and_written_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "pnpm-workspace.yaml").write_text("packages: []\n")
            (root / "a.ts").write_text("export {}\n")
            result = run_cli(root, "--apply", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)["plan"]
            self.assertEqual(plan["recommended"][0]["code"], "NATIVE_CONTEXT_BASELINE")
            self.assertTrue(plan["complexity_evidence"])
            markdown = (root / ".repomoor" / "recommendations.md").read_text()
            for item in plan["recommended"] + plan["optional_pilots"] + plan["skipped_details"]:
                self.assertIn(f"`{item['code']}`", markdown)


class WriterHardeningTests(unittest.TestCase):
    """P0-01: safe_create never writes outside the root, follows a symlink, or overwrites."""

    MODES = ("dir_fd", "path_walk")

    def _modes(self):
        return [m for m in self.MODES if m != "dir_fd" or fs.HAS_DIR_FD]

    def _dirs(self):
        base = tempfile.TemporaryDirectory()
        self.addCleanup(base.cleanup)
        b = Path(base.name).resolve()
        root, outside = b / "project", b / "outside"
        root.mkdir()
        outside.mkdir()
        return b, root, outside

    def _symlink(self, link: Path, target: Path, is_dir: bool = False) -> None:
        try:
            link.symlink_to(target, target_is_directory=is_dir)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")

    def test_lexically_invalid_paths_refused(self):
        for mode in self._modes():
            with self.subTest(mode=mode), mock.patch.object(fs, "HAS_DIR_FD", mode == "dir_fd"):
                base, root, _ = self._dirs()
                for rel in ("../escape.txt", "a/../../escape.txt", str(base / "abs.txt"), "", ".", "a//b.txt",
                            "a/./b.txt", "a\\b.txt", "C:/x.txt", "x\x00.txt", ".repomoor/"):
                    self.assertEqual(fs.safe_create(root, rel, "x"), "REFUSED: outside project", repr(rel))
                self.assertEqual(sorted(p.name for p in base.iterdir()), ["outside", "project"])
                self.assertEqual(list(root.iterdir()), [])

    def test_nested_directories_created_and_bytes_exact(self):
        for mode in self._modes():
            with self.subTest(mode=mode), mock.patch.object(fs, "HAS_DIR_FD", mode == "dir_fd"):
                _, root, _ = self._dirs()
                text = "naïve, ü ✓\nline 2\n"
                self.assertEqual(fs.safe_create(root, "a/b/c/d.md", text), "CREATED")
                self.assertEqual((root / "a/b/c/d.md").read_bytes(), text.encode("utf-8"))
                self.assertEqual(fs.safe_create(root, "a/b/c/d.md", text), "UNCHANGED (identical existing file)")
                self.assertIn("PRESERVED", fs.safe_create(root, "a/b/c/d.md", text.upper()))
                self.assertIn("PRESERVED", fs.safe_create(root, "a/b/c/d.md", text + "more"))
                self.assertEqual((root / "a/b/c/d.md").read_bytes(), text.encode("utf-8"))

    def test_file_where_directory_expected(self):
        for mode in self._modes():
            with self.subTest(mode=mode), mock.patch.object(fs, "HAS_DIR_FD", mode == "dir_fd"):
                _, root, _ = self._dirs()
                (root / ".repomoor").write_text("user file")
                self.assertEqual(fs.safe_create(root, ".repomoor/a.txt", "x"), "REFUSED: path parent is not a directory")
                self.assertEqual((root / ".repomoor").read_text(), "user file")

    def test_symlinked_parent_and_leaf_refused(self):
        for mode in self._modes():
            with self.subTest(mode=mode), mock.patch.object(fs, "HAS_DIR_FD", mode == "dir_fd"):
                _, root, outside = self._dirs()
                self._symlink(root / "linked", outside, is_dir=True)
                self.assertEqual(fs.safe_create(root, "linked/a.txt", "x"), "REFUSED: symlinked directory")
                (outside / "target.txt").write_text("outside")
                self._symlink(root / "leaf.txt", outside / "target.txt")
                self._symlink(root / "dangling.txt", outside / "never-created.txt")
                self.assertEqual(fs.safe_create(root, "leaf.txt", "x"), "REFUSED: existing symlink")
                self.assertEqual(fs.safe_create(root, "dangling.txt", "x"), "REFUSED: existing symlink")
                self.assertEqual(sorted(p.name for p in outside.iterdir()), ["target.txt"])
                self.assertEqual((outside / "target.txt").read_text(), "outside")

    def test_existing_directory_or_fifo_leaf_preserved_without_blocking(self):
        for mode in self._modes():
            with self.subTest(mode=mode), mock.patch.object(fs, "HAS_DIR_FD", mode == "dir_fd"):
                _, root, _ = self._dirs()
                (root / "dir.txt").mkdir()
                self.assertIn("PRESERVED", fs.safe_create(root, "dir.txt", "x"))
                if not hasattr(os, "mkfifo"):
                    continue
                os.mkfifo(root / "pipe.txt")
                result: list[str] = []
                worker = threading.Thread(target=lambda: result.append(fs.safe_create(root, "pipe.txt", "x")), daemon=True)
                worker.start()
                worker.join(5)
                self.assertFalse(worker.is_alive(), "safe_create blocked on a FIFO")
                self.assertIn("PRESERVED", result[0])

    def _swap_when_opening(self, root: Path, outside: Path, name: str):
        """Patch os.open so that, just before `name` is opened, .repomoor becomes a symlink to `outside`."""
        real_open, fired = os.open, []

        def hooked(path, *args, **kwargs):
            if not fired and os.path.basename(os.fspath(path)) == name:
                fired.append(True)
                os.rename(root / ".repomoor", root / ".moved")
                os.symlink(outside, root / ".repomoor", target_is_directory=True)
            return real_open(path, *args, **kwargs)
        return mock.patch("os.open", hooked), fired

    @unittest.skipUnless(fs.HAS_DIR_FD, "dir_fd traversal unavailable on this platform")
    def test_parent_swapped_for_symlink_mid_call_cannot_escape(self):
        for point in (".repomoor", "a.txt"):  # swap just before the parent open, then just before the leaf open
            with self.subTest(swap_before=point):
                _, root, outside = self._dirs()
                (root / ".repomoor").mkdir()
                try:
                    os.symlink(outside, root / ".probe")
                    os.unlink(root / ".probe")
                except (OSError, NotImplementedError):
                    self.skipTest("Symlinks unavailable")
                patcher, fired = self._swap_when_opening(root, outside, point)
                with patcher:
                    status = fs.safe_create(root, ".repomoor/a.txt", "x")
                self.assertTrue(fired, "swap hook never ran")
                self.assertEqual(list(outside.iterdir()), [], f"wrote outside the root ({status})")
                if point == ".repomoor":
                    self.assertEqual(status, "REFUSED: symlinked directory")
                else:
                    self.assertEqual(status, "CREATED")  # into the directory that was opened, now renamed
                    self.assertEqual((root / ".moved" / "a.txt").read_text(), "x")

    @unittest.skipUnless(fs.HAS_DIR_FD, "dir_fd traversal unavailable on this platform")
    def test_concurrent_symlink_swapping_never_escapes(self):
        _, root, outside = self._dirs()
        (root / ".repomoor").mkdir()
        try:
            os.symlink(outside, root / ".probe")
            os.unlink(root / ".probe")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        stop = threading.Event()

        def swapper():
            while not stop.is_set():
                try:
                    os.rename(root / ".repomoor", root / ".hold")
                    os.symlink(outside, root / ".repomoor", target_is_directory=True)
                    os.unlink(root / ".repomoor")
                    os.rename(root / ".hold", root / ".repomoor")
                except OSError:
                    pass
        worker = threading.Thread(target=swapper, daemon=True)
        worker.start()
        statuses = set()
        try:
            for i in range(400):
                statuses.add(fs.safe_create(root, f".repomoor/f{i}.txt", "x").split(" (")[0].split(":")[0])
        finally:
            stop.set()
            worker.join(5)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue(statuses <= {"CREATED", "REFUSED", "PRESERVED", "ERROR"}, statuses)

    @unittest.skipUnless(fs.HAS_DIR_FD, "dir_fd traversal unavailable on this platform")
    def test_symlinked_root_refused(self):
        _, root, outside = self._dirs()
        self._symlink(root / "rootlink", outside, is_dir=True)
        self.assertEqual(fs.safe_create(root / "rootlink", "a.txt", "x"), "REFUSED: symlinked directory")
        self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipUnless(fs.HAS_DIR_FD, "dir_fd traversal unavailable on this platform")
    def test_failed_write_removes_only_its_own_partial_file(self):
        _, root, _ = self._dirs()
        (root / "keep.txt").write_text("user")
        with mock.patch("os.write", side_effect=OSError(errno.ENOSPC, "No space left on device")):
            status = fs.safe_create(root, "new.txt", "x")
        self.assertTrue(status.startswith("ERROR: write failed"), status)
        self.assertFalse((root / "new.txt").exists())
        self.assertEqual((root / "keep.txt").read_text(), "user")


class ScanLimitTests(unittest.TestCase):
    """P0-03: bounded directory walking with visible truncation reasons."""

    def test_normal_repository_is_not_truncated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("pass\n")
            scan = cli.enumerate_repo(root, 1000, 6)
            self.assertEqual((scan["scan_truncated"], scan["truncation_reasons"], scan["dirs_unreadable"]), (False, [], 0))

    def test_directory_budget_bounds_the_walk(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for i in range(40):
                (root / f"d{i:02}" / "inner").mkdir(parents=True)
            scan = cli.enumerate_repo(root, 1000, 6, max_dirs=10)
            self.assertLessEqual(scan["dirs_examined"], 10)
            self.assertEqual(scan["truncation_reasons"], ["max_dirs"])
            self.assertTrue(scan["scan_truncated"])

    def test_wide_directory_listing_is_capped(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(scanner, "MAX_DIR_ENTRIES", 50):
            root = Path(d).resolve()
            for i in range(60):
                (root / f"f{i}.py").write_text("")
            scan = cli.enumerate_repo(root, 1000, 6)
            self.assertEqual(scan["files_examined"], 50)
            self.assertEqual(scan["truncation_reasons"], ["max_dir_entries"])

    def test_file_budget_reason_reported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for i in range(120):
                (root / f"f{i}.py").write_text("")
            self.assertEqual(cli.enumerate_repo(root, 100, 6)["truncation_reasons"], ["max_files"])

    @unittest.skipIf(not hasattr(os, "geteuid") or os.geteuid() == 0, "needs a non-root POSIX user")
    def test_unreadable_directory_counted_and_doctor_warns(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            locked = root / "locked"
            locked.mkdir()
            locked.chmod(0)
            try:
                self.assertEqual(cli.enumerate_repo(root, 1000, 6)["dirs_unreadable"], 1)
                codes = [x["code"] for x in json.loads(run_cli(root, "--doctor", "--json").stdout)["checks"]]
                self.assertIn("unreadable-directories", codes)
            finally:
                locked.chmod(0o755)

    def test_max_dirs_option_validated_and_applied(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for i in range(5):
                (root / f"d{i}").mkdir()
            self.assertEqual(run_cli(root, "--max-dirs", "0").returncode, 2)
            report = json.loads(run_cli(root, "--max-dirs", "2", "--json").stdout)
            self.assertEqual(report["scan"]["truncation_reasons"], ["max_dirs"])


class ParseLimitTests(unittest.TestCase):
    """P0-03: hostile manifests never crash, hang, or leak; problems are reported by path and code."""

    def _signals(self, files: dict[str, str]):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        root = Path(d.name).resolve()
        for rel, body in files.items():
            (root / rel).write_text(body)
        return root, cli.project_signals(root, cli.enumerate_repo(root, 1000, 6))

    def test_json_depth_limit(self):
        self.assertEqual(parsing.parse_json("[" * 64 + "]" * 64)[1], None)
        self.assertEqual(parsing.parse_json("[" * 65 + "]" * 65), (None, "too-deep"))
        self.assertEqual(parsing.parse_json('{"a": "' + "[" * 5000 + '"}'), ({"a": "[" * 5000}, None))
        self.assertEqual(parsing.parse_json('{"a": "\\"' + "[" * 100 + '"}')[1], None)
        self.assertEqual(parsing.parse_json("{nope"), (None, "invalid-json"))

    def test_package_json_problems_reported_by_code(self):
        cases = {
            "[" * 50000: "too-deep",
            '{"name": "SECRET-IN-MANIFEST", ': "invalid-json",
            '["SECRET-IN-MANIFEST"]': "not-object",
            json.dumps({"workspaces": ["apps/*"], "pad": "SECRET-IN-MANIFEST" * 20000}): "too-large",
        }
        for body, code in cases.items():
            with self.subTest(code=code):
                root, signals = self._signals({"package.json": body})
                self.assertEqual(signals["parse_issues"], [{"path": "package.json", "code": code}])
                result = run_cli(root, "--json")
                self.assertEqual(result.returncode, 0, result.stderr[-300:])
                self.assertNotIn("SECRET-IN-MANIFEST", result.stdout + result.stderr)

    def test_symlinked_manifest_reported_not_followed(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "package.json"
            target.write_text(json.dumps({"workspaces": ["*"]}))
            root, _ = self._signals({})
            try:
                (root / "package.json").symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            signals = cli.project_signals(root, cli.enumerate_repo(root, 1000, 6))
            self.assertEqual(signals["parse_issues"], [{"path": "package.json", "code": "not-regular-file"}])
            self.assertFalse(signals["workspace_detected"])

    def test_cargo_workspace_regex_is_linear_and_still_matches(self):
        root, signals = self._signals({"Cargo.toml": "\n" * 190_000})
        start = time.monotonic()
        cli.project_signals(root, cli.enumerate_repo(root, 1000, 6))
        self.assertLess(time.monotonic() - start, 2.0)
        for body in ("[workspace]\n", "[package]\n\n  [workspace]\nmembers = []\n", "\t[workspace]"):
            self.assertTrue(self._signals({"Cargo.toml": body})[1]["workspace_detected"], repr(body))
        self.assertFalse(self._signals({"Cargo.toml": "# [workspace]\n"})[1]["workspace_detected"])

    def test_parse_issues_reach_doctor_preview_and_context(self):
        root, _ = self._signals({"package.json": "[" * 1000})
        doctor = json.loads(run_cli(root, "--doctor", "--json").stdout)
        self.assertIn("parse-issues", [x["code"] for x in doctor["checks"]])
        self.assertIn("package.json (too-deep)", run_cli(root, "--non-interactive").stdout)
        self.assertEqual(run_cli(root, "--apply", "--json").returncode, 0)
        self.assertIn("`package.json` (too-deep)", (root / ".repomoor" / "PROJECT_CONTEXT.md").read_text())

    def test_hostile_answers_and_profile_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
            root = Path(d).resolve()
            answers = Path(a) / "answers.json"
            answers.write_text("[" * 16000)
            result = run_cli(root, "--answers", str(answers))
            self.assertEqual(result.returncode, 2)
            self.assertIn("nested too deeply", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            (root / ".repomoor").mkdir()
            for body in ("[" * 50000, json.dumps({"scan": []}), "x" * 200_000):
                (root / ".repomoor" / "project-profile.json").write_text(body)
                result = run_cli(root, "--doctor", "--json")
                self.assertEqual(result.returncode, 0, result.stderr[-300:])
                self.assertIn("profile-unreadable", [x["code"] for x in json.loads(result.stdout)["checks"]])


class RulePreservationTests(unittest.TestCase):
    """P0-02: every known instruction location, root or nested, blocks --integrate for every
    agent selection, and no pre-existing byte changes."""

    @staticmethod
    def _layouts() -> dict[str, dict[str, str]]:
        layouts: dict[str, dict[str, str]] = {}
        for rel in sorted(cli.INSTRUCTION_PATHS):
            is_dir = "." not in Path(rel).name or rel.endswith(("/rules", "/steering", "/instructions", "/prompts"))
            layouts[f"root:{rel}"] = {(f"{rel}/rule.md" if is_dir else rel): "existing rule\n"}
        layouts.update({
            "nested:AGENTS.md": {"apps/web/AGENTS.md": "web rules\n", "apps/web/a.ts": "x"},
            "nested:CLAUDE.md": {"packages/core/CLAUDE.md": "core rules\n"},
            "nested:CLAUDE.local.md": {"svc/CLAUDE.local.md": "mine\n"},
            "nested:GEMINI.md": {"svc/GEMINI.md": "gemini\n"},
            "nested:lowercase agents.md": {"apps/api/agents.md": "lower\n"},
            "nested:.cursor/rules": {"apps/web/.cursor/rules/ui.mdc": "---\nglobs: '*.tsx'\n---\n"},
        })
        return layouts

    def _snapshot(self, root: Path) -> dict[str, bytes]:
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_every_location_blocks_integration_for_every_agent_choice(self):
        agent_choices = [c for c, _ in cli.QUESTIONS["agents"][1]]
        for label, files in self._layouts().items():
            with tempfile.TemporaryDirectory() as d:
                root = Path(d).resolve()
                for rel, body in files.items():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    (root / rel).write_text(body)
                before = self._snapshot(root)
                scan = cli.enumerate_repo(root, 1000, 6)
                signals = cli.project_signals(root, scan)
                self.assertTrue(signals["instruction_files"], label)
                for agents in agent_choices:
                    with self.subTest(layout=label, agents=agents):
                        answers = {**DEFAULTS, "agents": agents, "future_project": "existing"}
                        plan = cli.make_recommendations(scan, signals, answers)
                        artifacts, notices = cli.artifact_candidates(root, scan, signals, answers, plan, True)
                        self.assertTrue(all(rel.startswith(".repomoor/") for rel in artifacts), list(artifacts))
                        self.assertTrue(any("integration skipped" in n for n in notices), notices)
                        for rel, body in artifacts.items():
                            cli.safe_create(root, rel, body)
                        after = self._snapshot(root)
                        self.assertEqual({k: v for k, v in after.items() if not k.startswith(".repomoor/")}, before)

    def test_end_to_end_nested_rules_block_cli_integration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "apps" / "web").mkdir(parents=True)
            (root / "apps" / "web" / "AGENTS.md").write_text("scoped\n")
            report = json.loads(run_cli(root, "--apply", "--integrate", "--json").stdout)
            self.assertEqual(report["signals"]["instruction_files"],
                             [{"path": "apps/web/AGENTS.md", "scope": "nested", "description": "Scoped agent instructions"}])
            self.assertNotIn("AGENTS.md", report["apply_results"])
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertIn("apps/web/AGENTS.md", " ".join(report["notices"]))
            self.assertIn("`apps/web/AGENTS.md`", (root / ".repomoor" / "PROJECT_CONTEXT.md").read_text())
            doctor = json.loads(run_cli(root, "--doctor", "--json").stdout)
            self.assertIn("nested-instructions", [x["code"] for x in doctor["checks"]])

    def test_truncated_scan_blocks_integration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for i in range(5):
                (root / f"d{i}").mkdir()
            report = json.loads(run_cli(root, "--apply", "--integrate", "--max-dirs", "2", "--json").stdout)
            self.assertNotIn("AGENTS.md", report["apply_results"])
            self.assertTrue(any("scan was truncated" in n for n in report["notices"]), report["notices"])
            self.assertFalse((root / "AGENTS.md").exists())

    def test_clean_repository_still_integrates(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "apps" / "web").mkdir(parents=True)
            (root / "apps" / "web" / "README.md").write_text("not a rule file\n")
            report = json.loads(run_cli(root, "--apply", "--integrate", "--json").stdout)
            self.assertEqual(report["apply_results"].get("AGENTS.md"), "CREATED")
            self.assertEqual(report["signals"]["instruction_files"], [])

    def test_root_case_variant_detected_on_any_filesystem(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            (root / "agents.md").write_text("lowercase root rules\n")
            signals = cli.project_signals(root, cli.enumerate_repo(root, 1000, 6))
            self.assertEqual(len(signals["instruction_files"]), 1, signals["instruction_files"])  # no duplicate on macOS
            self.assertEqual(signals["instruction_files"][0]["scope"], "root")
            report = json.loads(run_cli(root, "--apply", "--integrate", "--json").stdout)
            self.assertNotIn("AGENTS.md", report["apply_results"])
            self.assertEqual((root / "agents.md").read_text(), "lowercase root rules\n")

    def test_vendored_and_skipped_directories_do_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d).resolve()
            for rel in ("node_modules/pkg/AGENTS.md", "vendor/lib/CLAUDE.md", ".git/AGENTS.md"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("third party\n")
            self.assertEqual(cli.enumerate_repo(root, 1000, 6)["nested_rule_paths"], [])

    def test_nested_rule_list_is_bounded(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(scanner, "MAX_NESTED_RULES", 3):
            root = Path(d).resolve()
            for i in range(5):
                (root / f"p{i}").mkdir()
                (root / f"p{i}" / "AGENTS.md").write_text("x")
            scan = cli.enumerate_repo(root, 1000, 6)
            self.assertEqual(len(scan["nested_rule_paths"]), 3)
            self.assertIn("max_nested_rules", scan["truncation_reasons"])

    def test_no_global_paths_in_registry(self):
        for rel in cli.AGENT_PATHS:
            self.assertFalse(rel.startswith(("~", "/")) or ".." in rel, rel)


class ModuleBoundaryTests(unittest.TestCase):
    """v0.3 split: keep layering, stdlib-only imports, and all writes inside fs.py."""

    PKG = BASE / "src" / "repomoor"
    # Internal modules each module may import. cli is the only composition root.
    ALLOWED = {
        "constants": set(), "fs": set(), "parsing": set(), "recommender": set(), "catalog": set(),
        "questions": {"parsing"}, "scanner": {"constants", "fs", "parsing"}, "report": {"constants", "fs"},
        "doctor": {"constants", "fs", "parsing"},
        "cli": {"catalog", "constants", "doctor", "fs", "parsing", "questions", "recommender", "report", "scanner"},
        "__init__": set(), "__main__": {"cli"},
    }
    # Explicit stdlib allowlist (works on every supported Python). Process, network and
    # deletion modules such as subprocess, socket, urllib or shutil are deliberately absent.
    STDLIB_ALLOWED = {"__future__", "argparse", "collections", "errno", "importlib", "json", "os", "pathlib", "re", "stat", "sys", "typing"}
    WRITE_CALLS = {"write_text", "write_bytes", "mkdir", "makedirs", "fdopen", "rename", "replace", "unlink", "rmdir", "symlink_to", "touch", "chmod"}

    def _modules(self):
        for path in sorted(self.PKG.glob("*.py")):
            yield path.stem, ast.parse(path.read_text(encoding="utf-8"))

    def test_every_module_has_a_layer(self):
        self.assertEqual({name for name, _ in self._modules()}, set(self.ALLOWED))

    def test_imports_follow_layers_and_stay_stdlib(self):
        for name, tree in self._modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level:
                    target = (node.module or "").split(".")[0]
                    self.assertIn(target, self.ALLOWED[name], f"{name} imports .{target}")
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    roots = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [node.module.split(".")[0]]
                    for root in roots:
                        self.assertIn(root, self.STDLIB_ALLOWED, f"{name} imports {root}; extend the allowlist only for stdlib modules")

    def test_recommender_is_pure(self):
        tree = ast.parse((self.PKG / "recommender.py").read_text(encoding="utf-8"))
        imported = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
        self.assertEqual(imported - {"annotations"}, {"Any"})
        self.assertNotIn("open", {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)})

    def test_only_fs_writes_files(self):
        for name, tree in self._modules():
            if name == "fs":
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Attribute):
                    self.assertNotIn(func.attr, self.WRITE_CALLS, f"{name} calls .{func.attr}()")
                    self.assertFalse(func.attr == "open" and isinstance(func.value, ast.Name) and func.value.id == "os", f"{name} calls os.open")
                if isinstance(func, ast.Name) and func.id == "open" or isinstance(func, ast.Attribute) and func.attr == "open":
                    mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
                    if mode is not None:
                        self.assertIsInstance(mode, ast.Constant, f"{name}: non-literal open mode")
                        self.assertFalse(set(mode.value) & set("wax+"), f"{name} opens for writing")

    def test_cli_reexports_v02_names(self):
        for attr in ("enumerate_repo", "project_signals", "make_recommendations", "safe_create", "safe_read",
                     "QUESTIONS", "REASON_CODES", "load_answers_file", "check_project", "load_catalog", "main", "VERSION"):
            self.assertTrue(hasattr(cli, attr), attr)


if __name__ == "__main__":
    unittest.main()
