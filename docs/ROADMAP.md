# Roadmap

All unchecked items are **planned, not shipped**. Priorities can change based on community feedback.

## v0.1.0: first public preview (current)

- [x] Zero-install Python CLI (standard library only) with a POSIX shell launcher.
- [x] Filename and manifest discovery, a short adaptive questionnaire, and `--answers FILE` for repeatable runs.
- [x] Detection of existing agent rules and settings at the root and in subfolders, without reading global settings.
- [x] Minimal stack recommendations with a reason code and evidence for every decision. Nothing is installed.
- [x] Preview by default, create-only `--apply`, and `--integrate` that refuses whenever rules already exist.
- [x] JSON output, a 19-tool research catalog, and a read-only `--doctor`.
- [x] Race-safe file writer on Linux and macOS, bounded parsing and scan limits.
- [x] Offline tests, including golden-output tests, on Linux, macOS and Windows.

## Next

- [ ] Per-detection confidence (`observed`, `inferred`, `unknown`) with evidence paths.
- [ ] Better parsing for more ecosystems: Yarn, Nx, Turborepo, Python monorepos, Java build systems.
- [ ] Service-level profiles for mixed-language repositories.
- [ ] A published JSON Schema for the answers file.
- [ ] Windows: junction handling and a race-safe writer.
- [ ] A safe `--refresh` that shows exact changes and never overwrites without separate approval.

## v0.4: Declarative integration planning

- [ ] Implement typed adapters with a policy engine and dry-run-only install plans.
- [ ] Start with a compatibility auditor for RTK, a Trail-Code project-local planning adapter and a graph adapter.
- [ ] Model existing MCP tools without printing secrets or overwriting config.
- [ ] Require pinned version, license check, capabilities, network and hook effect declaration.
- [ ] Create per-tool conflict resolution reports rather than silent installation.

## v0.5: Controlled application and rollback (security gated)

- [ ] Transaction journal; explicit file ownership and rollback.
- [ ] Harden path handling against concurrent symlink/file replacement.
- [ ] Prove all default effects stay inside project in isolated platform tests.
- [ ] Runtime health checks only for integrations the user explicitly authorized.
- [ ] A clear opt-in consent UX for any subprocess or downloaded binaries.

## v0.6: Benchmark and optimization loop

- [ ] Pluggable task benchmark runner (Claude Code / Cursor where APIs and permissions allow).
- [ ] Accurate accounting for cache reads/writes, time, attempts and tool invocation.
- [ ] Task acceptance rubric and reproducible sample repos.
- [ ] Report cost per accepted task and missing dependency incidents.
- [ ] Evidence-based recommendations and a 'remove redundant tool' advisor.

## Long-term research

- Rule deduplication without violating priority/ownership of existing instructions.
- Local-on-disk architectural decision memory; update only after human validation.
- Service-scoped indexing based on topology and task-level demand.
- An explainable policy engine that chooses one graph, one memory strategy, at most one specialist layer.
- Cross-agent compatibility profiles, continuously tested against changing vendor formats.

## Release gate

No auto-install adapter ships until it passes the [adapter threat matrix](ADAPTER_SPEC.md) and [safety requirements](SAFETY.md). No token-reduction claims ship without the [benchmark protocol](BENCHMARKS.md) and published replicable task-level evidence.
