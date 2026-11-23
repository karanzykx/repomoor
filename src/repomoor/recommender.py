"""Pure recommendation policy: scan + signals + answers -> plan. No I/O."""
from __future__ import annotations

from typing import Any

# Stable reason codes. Codes are part of the JSON contract: never rename or reuse one;
# add new codes instead. Each maps to the outcome it is emitted with.
REASON_CODES: dict[str, tuple[str, str]] = {
    "NATIVE_CONTEXT_BASELINE": ("recommended", "Native rules and docs are the zero-dependency baseline for every repository."),
    "GRAPH_REUSE_EXISTING": ("recommended", "A project-local graph/index integration is already configured; reuse it."),
    "GRAPH_SKIP_DUPLICATE": ("skipped", "A graph is already configured; a second overlapping graph is not added."),
    "GRAPH_SKIP_BLANK": ("skipped", "The repository has no code yet, so there is nothing to index."),
    "GRAPH_PILOT_DISCOVERY": ("recommended", "Complex repository with repeated-discovery or unknown pain: pilot a mapping/decision tool."),
    "GRAPH_PILOT_IMPACT": ("recommended", "Complex repository where change impact or correctness matters most: pilot an impact graph."),
    "GRAPH_ALT_IMPACT": ("optional", "Impact-focused graph offered as an alternative to the discovery pilot, not an addition."),
    "GRAPH_ALT_DISCOVERY": ("optional", "Discovery-focused tool offered as an alternative to the impact pilot, not an addition."),
    "GRAPH_BENCHMARK_LATER": ("optional", "Complex repository but no stated discovery bottleneck: benchmark a graph later."),
    "MAP_LIGHTWEIGHT": ("optional", "Mid-sized repository with discovery/impact pain: try a light map before an MCP graph."),
    "GRAPH_SKIP_SCALE": ("skipped", "Native search is a reasonable baseline at this scale and workload."),
    "OUTPUT_SKIP_DUPLICATE": ("skipped", "Output compression is already configured in the project; do not duplicate it."),
    "OUTPUT_PILOT_TERMINAL": ("optional", "Large terminal output was named as the main waste: pilot output compression."),
    "OUTPUT_SKIP_UNMEASURED": ("skipped", "Output compression waits until tool output is measured as a bottleneck."),
    "BROWSER_PILOT": ("optional", "Browser work was named, or a web project is planned or prioritised for speed."),
    "REASSESS_AFTER_CODE": ("optional", "Blank repository: rerun once real code and topology exist."),
}


def complexity_evidence(scan: dict[str, Any], signals: dict[str, Any], answers: dict[str, str]) -> list[str]:
    """Every condition that made the repository count as complex (empty list = not complex)."""
    count = scan["sampled_source_files"]
    languages = len([x for x, n in scan["source_counts"].items() if n >= 5])
    found: list[str] = []
    if signals["workspace_detected"]:
        found.append("signal:workspace_detected=" + ",".join(signals.get("workspace_evidence") or ["yes"]))
    if answers["scope"] == "yes":
        found.append("answer:scope=yes")
    if answers["future_project"] == "multi":
        found.append("answer:future_project=multi")
    if count >= 350:
        found.append(f"scan:sampled_source_files={count}>=350")
    elif count >= 120 and languages >= 2:
        found.append(f"scan:sampled_source_files={count}>=120 with {languages} languages")
    return found


def make_recommendations(scan: dict[str, Any], signals: dict[str, Any], answers: dict[str, str]) -> dict[str, Any]:
    count = scan["sampled_source_files"]
    why_complex = complexity_evidence(scan, signals, answers)
    is_complex = bool(why_complex)
    blank = signals["blank_or_uninitialized"]
    selected: list[dict[str, Any]] = []
    optional: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    def entry(code: str, evidence: list[str], **fields: Any) -> dict[str, Any]:
        assert code in REASON_CODES, code
        return {**fields, "code": code, "evidence": evidence}

    def skip(code: str, reason: str, evidence: list[str]) -> None:
        skipped.append(entry(code, evidence, reason=reason))

    pain = f"answer:pain={answers['pain']}"
    selected.append(entry("NATIVE_CONTEXT_BASELINE", ["policy:always"],
        name="Native project context + curated architecture decisions",
        purpose="Small, accurate rules and relevant project docs instead of a large always-on prompt",
        reason="No third-party dependency; useful for any repo size. Preserve any existing agent instructions.",
        installation="None; create or edit docs manually only where needed."))
    graphs = signals["configured_graph_tools"]
    outputs = signals["configured_output_tools"]
    graph_ev = ["signal:configured_graph_tools=" + ",".join(graphs)]
    if graphs:
        selected.append(entry("GRAPH_REUSE_EXISTING", graph_ev,
            name="Existing project graph/index integration",
            purpose="Reuse current retrieval tooling",
            reason="Detected local signs of " + ", ".join(graphs) + ". Avoid a second overlapping graph.",
            installation="None; verify the existing index is fresh and used by the agent."))
        skip("GRAPH_SKIP_DUPLICATE", "Do not automatically add Trail-Code, GitNexus, or another graph alongside an existing graph.", graph_ev)
    elif blank:
        skip("GRAPH_SKIP_BLANK", "No code graph for an empty repository. Add it only after code size or task patterns justify indexing.", ["signal:blank_or_uninitialized=true"])
    elif is_complex and answers["pain"] in ("rediscovery", "unknown"):
        ev = why_complex + [pain]
        selected.append(entry("GRAPH_PILOT_DISCOVERY", ev,
            name="Trail-Code (optional pilot, not auto-install)",
            purpose="Symbol/dependency mapping plus reusable decisions",
            reason="Cross-package/repository exploration or repeated discovery may benefit from targeted context. Validate against native search.",
            installation="Review `trail init --dry-run` and project-only `trail init --no-global` after checking its documentation and effects."))
        optional.append(entry("GRAPH_ALT_IMPACT", ev, name="code-review-graph", reason="Alternative (not an addition) when change impact and targeted test selection dominate."))
    elif is_complex and (answers["pain"] == "impact" or answers["priority"] == "correctness"):
        ev = why_complex + ([pain] if answers["pain"] == "impact" else ["answer:priority=correctness"])
        selected.append(entry("GRAPH_PILOT_IMPACT", ev,
            name="code-review-graph (optional pilot, not auto-install)",
            purpose="Change impact, graph relationships and relevant tests",
            reason="Large/multi-service repositories with impact-analysis needs warrant a controlled graph trial.",
            installation="Read its project-local integration instructions and audit planned config changes before setup."))
        optional.append(entry("GRAPH_ALT_DISCOVERY", ev, name="Trail-Code", reason="Alternative if recurring architectural decisions are a bigger waste than dependency tracing."))
    elif is_complex:
        optional.append(entry("GRAPH_BENCHMARK_LATER", why_complex + [pain], name="Trail-Code OR code-review-graph", reason="Useful to benchmark after code exists; not compulsory without an observed discovery bottleneck."))
    elif answers["pain"] in ("impact", "rediscovery") and count >= 80:
        optional.append(entry("MAP_LIGHTWEIGHT", [pain, f"scan:sampled_source_files={count}>=80"], name="Sprout or codemap", reason="Try a simpler mapping layer before an MCP graph; compare it with plain search."))
    else:
        skip("GRAPH_SKIP_SCALE", "Defer additional code graphs: native search is a reasonable baseline for this scale/workload.",
             ["signal:complexity=small-or-early-stage", f"scan:sampled_source_files={count}", pain])

    if outputs:
        skip("OUTPUT_SKIP_DUPLICATE", "Project-local output compression configuration already detected: " + ", ".join(outputs) + ". Do not duplicate it.",
             ["signal:configured_output_tools=" + ",".join(outputs)])
    elif answers["pain"] == "terminal":
        optional.append(entry("OUTPUT_PILOT_TERMINAL", [pain], name="RTK", reason="Pilot command-output compression. Its project-local init may edit CLAUDE.md; inspect first, never run automatically."))
    else:
        skip("OUTPUT_SKIP_UNMEASURED", "Do not add RTK/Headroom until logs/tool outputs are measured as a real bottleneck.", [pain])
    browser_ev = []
    if answers["pain"] == "browser":
        browser_ev.append(pain)
    if signals["frontend_detected"] and answers["priority"] == "speed":
        browser_ev += ["signal:frontend_detected=true", "answer:priority=speed"]
    if answers["future_project"] == "web":
        browser_ev.append("answer:future_project=web")
    if browser_ev:
        optional.append(entry("BROWSER_PILOT", browser_ev, name="agent-browser", reason="Consider only for repeated browser automation, screenshots and UI verification."))
    if blank:
        optional.append(entry("REASSESS_AFTER_CODE", ["signal:blank_or_uninitialized=true"], name="Reassess after initial code", reason="Run this CLI again when actual repository topology, tools and files exist."))
    return {
        "complexity_assessment": "potentially-complex" if is_complex else "small-or-early-stage",
        "complexity_evidence": why_complex,
        "no_automatic_install": True,
        "recommended": selected,
        "optional_pilots": optional,
        # Kept as plain strings for v0.2 consumers; the coded form is in skipped_details.
        "deliberately_skipped": [x["reason"] for x in skipped],
        "skipped_details": skipped,
        "measurement": [
            "Successful task completion and regression-test correctness",
            "Full-session billed input/output tokens and prompt-cache usage",
            "Repeated tool calls, elapsed time, and dependency misses",
            "Index refresh overhead, agent tool usage and configuration maintenance",
        ],
    }
