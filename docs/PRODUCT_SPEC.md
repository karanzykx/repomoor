# Product specification (PRD)

**Product:** RepoMoor | **Status:** Alpha / evolving | **Last reviewed:** 2026-11-18

## Problem statement

AI coding tools repeatedly scan unrelated files, re-investigate architectural decisions, and handle verbose terminal output. Installing a blanket collection of MCP servers can increase overhead, tool confusion, and maintenance while providing no proven gain. Project size and architecture differ, so a universal stack is inappropriate.

## Intended users

- Solo engineer starting a blank project who wants sensible defaults.
- Engineer inheriting an existing repository with Cursor/Claude configuration already in place.
- Technical lead working on a polyglot monorepo or multiple services.
- Engineer paying for tokens or constrained by plan usage who wants empirical improvements.
- Contributor evaluating a new tool without compromising existing agent rules.

## Jobs to be done

1. When I start a project, analyze repository structure without requiring me to know the stack.
2. Ask only a handful of meaningful questions through selectable CLI options.
3. Detect what is **already configured in this project**, not on my machine.
4. Respect pre-existing instructions and MCP settings; do not override, mutate, or merge them silently.
5. Recommend only the tools whose expected benefits justify their complexity.
6. Preserve the reasoning and a lightweight project description for future sessions.
7. Later, diagnose failures or changes and measure actual task-level savings.

## Core product principles

- Local-first; no cloud requirement.
- Explicit intent for any filesystem write.
- Human-readable reasoning and reversible change proposals.
- Accuracy and completion rate are more important than raw input compression.
- Prefer existing/native capabilities over extra dependencies.
- Fail closed when local-only effects cannot be verified.

## Current user journeys

### A. Blank repository

Run `python3 repomoor.py /repo`. CLI notices no language/manifest evidence and asks intended project shape. It recommends a minimal native-context foundation, **no code graph yet**, and reassessment after code exists. `--apply` produces a create-only report.

### B. Existing project with rules

CLI detects existing `AGENTS.md`, `CLAUDE.md`, `.cursor/rules` etc. `--apply --integrate` does not touch them or add competing agent instructions. Reports can be manually linked by the maintainer if desired.

### C. Multi-service monorepo

Workspace files and multiple manifests suggest complexity; questions determine whether extra dependency navigation is likely helpful. CLI proposes *one* graph pilot and an A/B test, not an automatic multi-tool install.

### D. Rerun after evolution

`--doctor` checks whether known manifests or source-language counts changed, then recommends reviewing earlier reports. Actual reports remain unmodified. A future version will add an explicit, reviewed refresh operation with backups.

## Functional requirements and current status

| ID | Requirement | Status |
|---|---|---|
| FR-01 | Run from arbitrary target repository | Shipped |
| FR-02 | Blank repo / common languages / workspace discovery | Shipped heuristics |
| FR-03 | Numbered adaptive CLI questions | Shipped |
| FR-04 | JSON preview without writes | Shipped |
| FR-05 | Identify known local agent instructions and MCP markers | Shipped heuristics |
| FR-06 | Explain a minimal recommended stack | Shipped |
| FR-07 | Never overwrite files or follow child symlinks | Shipped, regression-tested |
| FR-08 | Project-local create-only context and plan | Shipped |
| FR-09 | Read-only health check | Shipped basic version |
| FR-10 | All 19 tools available as informational catalog | Shipped |
| FR-11 | Safe, versioned adapter installation with dry-run diffs | Not implemented |
| FR-12 | Confidence scores and evidence per detector | Planned |
| FR-13 | Accurate config parsing and detection across nested packages | Planned |
| FR-14 | Execute isolated, repeatable AI task benchmarks | Planned |
| FR-15 | Guided project-only uninstall and rollback | Planned |
| FR-16 | Non-interactive YAML/JSON policy file | Planned |

## Non-functional requirements

Security: no execution of untrusted project content, no external network calls, no personal environment inspection, no deliberate secret disclosure. Portability: Python >=3.10 and stdlib operation. Maintainability: machine-readable tool catalog, tests, explicit architecture notes. UX: default preview, brief options, no confusing forced questions in unattended mode.

## Acceptance checklist for the alpha

- [x] Works on an empty directory.
- [x] Finds workspace indicators in a representative monorepo.
- [x] Reads no data through a symlink to another directory.
- [x] Existing agent rules are not modified.
- [x] Existing report files cannot be silently overwritten.
- [x] A sample MCP credential is not emitted in JSON output.
- [x] An untrusted `package.json` postinstall script is never run.
- [x] Catalog contains exactly the 19 named research candidates.
- [x] `--doctor` is read-only.
- [ ] Simulated and real hostile filesystem race tests complete (future hardening).
- [ ] End-to-end benchmark results independently replicated (future).

## Definition of success (future measurable goals)

- At least 10% reduction in median total cost per *correctly completed* real task for a representative subgroup, with no statistically meaningful loss in correctness.
- Less than one extra interaction required for confident common-repository recommendations.
- Zero unapproved writes in integration test matrix (Linux, macOS, Windows).
- Clear explanation of every recommendation's evidence, cost, overlaps, and rollback path.

These are goals, **not achieved measurements**.
