#!/usr/bin/env python3
"""Project-local, non-destructive AI coding stack advisor (stdlib only).

Never follows project symlinks; never installs/executes third-party software;
never changes an existing file. Discovery uses names and bounded local manifests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Re-exported so `from repomoor import cli; cli.<name>` keeps working for v0.2 callers and tests.
from .catalog import load_catalog
from .constants import OUTPUT_DIR, VERSION
from .doctor import check_project
from .fs import MAX_MANIFEST_BYTES, is_local_regular_file, local_exists, read_bounded, safe_create, safe_read
from .parsing import MAX_JSON_DEPTH, parse_json
from .questions import (ANSWERS_VERSION_KEY, MAX_ANSWERS_BYTES, QUESTIONS, AnswersError,
                        answers_from_user, choose, load_answers_file)
from .recommender import REASON_CODES, complexity_evidence, make_recommendations
from .report import artifact_candidates, context_markdown, evidence_text, rec_markdown
from .scanner import (MAX_DIR_ENTRIES, MAX_DIRS_DEFAULT, AGENT_PATHS, INSTRUCTION_PATHS, NESTED_RULE_NAMES, EXISTING_GRAPH_KEYWORDS, MANIFEST_NAMES, OUTPUT_KEYWORDS,
                      REPO_CONFIG_PATHS, SKIP_DIRS, SOURCE_EXTS, contains_keyword_in_config,
                      enumerate_repo, project_signals)


def main() -> int:
    parser = argparse.ArgumentParser(description="Project-only AI coding tool advisor. No installs; no overwrites; stdlib-only.")
    parser.add_argument("root", nargs="?", default=".", help="Project directory (default: current directory)")
    parser.add_argument("--catalog", action="store_true", help="List informational tool catalog without reading a project")
    parser.add_argument("--doctor", action="store_true", help="Inspect project-local configuration and saved profile without writing")
    parser.add_argument("--apply", action="store_true", help=f"Create new {OUTPUT_DIR}/ report files; existing files are preserved")
    parser.add_argument("--integrate", action="store_true", help="With --apply, create minimal root agent instructions ONLY if no existing rules")
    parser.add_argument("--non-interactive", action="store_true", help="Use conservative defaults for unanswered questions")
    parser.add_argument("--answers", metavar="FILE", help="Read questionnaire answers from a small JSON file (strictly validated; read-only)")
    parser.add_argument("--json", action="store_true", help="Print preview as JSON (implies non-interactive; no writes unless --apply)")
    parser.add_argument("--max-files", type=int, default=12000, help="Maximum number of files to inspect (default: 12000)")
    parser.add_argument("--max-depth", type=int, default=6, help="Maximum directory depth (default: 6)")
    parser.add_argument("--max-dirs", type=int, default=MAX_DIRS_DEFAULT, help=f"Maximum number of directories to visit (default: {MAX_DIRS_DEFAULT})")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()
    if args.catalog:
        if args.apply or args.integrate or args.doctor:
            parser.error("--catalog cannot be combined with --apply, --integrate, or --doctor")
        info = load_catalog()
        if args.json:
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print("RepoMoor research catalog (not a tool installer)")
            for item in info["tools"]:
                print(f"  {item['name']:<24} {item['category']:<20} {item['url']}")
            print("\nVerify current licensing, maintenance, and project-only install behavior upstream.")
        return 0
    if args.doctor and (args.apply or args.integrate):
        parser.error("--doctor is read-only and cannot be combined with --apply or --integrate")
    if args.integrate and not args.apply:
        parser.error("--integrate requires --apply")
    if args.max_files < 100 or args.max_depth < 0 or args.max_depth > 15:
        parser.error("--max-files must be at least 100 and --max-depth must be 0..15")
    if not 1 <= args.max_dirs <= 200_000:
        parser.error("--max-dirs must be 1..200000")
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        parser.error("Project path does not exist or is not a directory")
    preset: dict[str, str] | None = None
    if args.answers is not None:
        if args.doctor:
            parser.error("--answers cannot be combined with --doctor")
        try:
            preset = load_answers_file(Path(args.answers).expanduser())
        except AnswersError as exc:
            parser.error(f"--answers: {exc}. No files changed.")
    scan = enumerate_repo(root, args.max_files, args.max_depth, args.max_dirs)
    signals = project_signals(root, scan)
    if args.doctor:
        report = check_project(root, scan, signals)
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print("RepoMoor project health check (read-only)")
            for item in report["checks"]:
                print(f"  [{item['level'].upper():4}] {item['message']}")
            print(f"Warnings: {report['warning_count']}. No files changed.")
        return 0
    interactive = (not args.non_interactive and not args.json and sys.stdin.isatty())
    if not interactive and not args.json and not args.non_interactive and preset is None:
        print("No interactive terminal detected: using conservative defaults. Run in a terminal for questions.")
    answers, answer_sources = answers_from_user(signals, scan, interactive, preset, quiet=args.json)
    plan = make_recommendations(scan, signals, answers)
    artifacts, notices = artifact_candidates(root, scan, signals, answers, plan, args.integrate)
    report = {"root": str(root), "scan": scan, "signals": signals, "answers": answers, "answer_sources": answer_sources, "plan": plan, "files_to_create_if_applied": list(artifacts), "notices": notices}
    if not args.json:
        print("\n=== Recommendation preview ===")
        print("Project:", root)
        print("Sampled source files:", scan["sampled_source_files"], f"(truncated: {', '.join(scan['truncation_reasons'])})" if scan["scan_truncated"] else "")
        if signals["parse_issues"]:
            print("Skipped or unparsable files:", ", ".join(f"{x['path']} ({x['code']})" for x in signals["parse_issues"]))
        print("Architecture:", plan["complexity_assessment"], "(" + ("; ".join(plan["complexity_evidence"]) or "no complexity trigger matched") + ")")
        if signals["configured_graph_tools"]:
            print("Detected graph integration(s):", ", ".join(signals["configured_graph_tools"]))
        if signals["configured_output_tools"]:
            print("Detected output tool(s):", ", ".join(signals["configured_output_tools"]))
        print("\nFoundation / pilots:")
        for x in plan["recommended"]:
            print("  +", x["name"], f"[{x['code']}]")
            print("    ", x["reason"])
            print("     evidence:", "; ".join(x["evidence"]))
        print("\nOptional:")
        for x in plan["optional_pilots"]:
            print("  ?", x["name"], f"[{x['code']}]:", x["reason"])
            print("     evidence:", "; ".join(x["evidence"]))
        print("\nIntentionally skipped:")
        for item in plan["skipped_details"]:
            print("  -", f"[{item['code']}]", item["reason"])
        for n in notices:
            print("\nNOTICE:", n)
        print("\nPlanned report files:")
        for rel in artifacts:
            print("  ", rel, "(already exists)" if local_exists(root, rel) else "(new)")
    if args.apply:
        if not args.json:
            print("\n=== Apply: create-new-files only ===")
        result: dict[str, str] = {}
        for rel, contents in artifacts.items():
            result[rel] = safe_create(root, rel, contents)
            if not args.json:
                print(" ", rel, ":", result[rel])
        report["apply_results"] = result
        if any(status.startswith("ERROR") or status.startswith("REFUSED") for status in result.values()):
            if args.json:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1
    elif not args.json:
        print("\nPreview complete. Nothing changed. To create the report, rerun with --apply.")
        print("To also create minimal instructions only where none exist: --apply --integrate")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
