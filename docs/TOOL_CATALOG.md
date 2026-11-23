# Candidate tool catalog: all 19 repositories

**Snapshot / review date:** 2026-11-18. This document captures research hypotheses to evaluate, **not independent certification of performance, license, safety, security, maintenance, or project-local installation**. The bundled [machine-readable catalog](../src/repomoor/data/tools.json) can be printed using `python3 repomoor.py --catalog --json`.

## The taxonomy

The tools are **not directly interchangeable**:

1. **Graph / structural navigation:** retrieve just the relevant call sites, modules, dependency paths, or change impact.
2. **Memory / team knowledge:** retain decisions and prior discoveries across sessions.
3. **Symbol retrieval / lightweight maps:** cheap targeted lookup without a heavyweight graph.
4. **Output compression:** shrink terminal/log/tool output while preserving the signal needed for correctness.
5. **Context export:** package repository excerpts for an external model/review session.
6. **Specialist agent tools:** browser automation or a complete alternative coding agent.

## Every candidate

| Tool | Category | Hypothesis worth testing | Caveat or overlap |
|---|---|---|---|
| [Graphify](https://github.com/Graphify-Labs/graphify) | Graph | Map code and adjacent project assets | Broad indexing may be unnecessary for small repos |
| [GitNexus](https://github.com/abhigyanpatwari/GitNexus) | Graph | Trace execution flow / blast radius | Check current commercial licensing and indexing cost |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Graph | Rich code and configuration graph via MCP | Independent task-level results vary; verify coverage |
| [code-review-graph](https://github.com/tirth8205/code-review-graph) | Impact analysis | Target change impacts and tests | Competes with other graph providers; benchmarks need replication |
| [Trail-Code](https://github.com/trailhq/Trail-Code) | Graph + memory | Reduce re-exploration *and* repeat decisions | Investigate project-only initialization; default setup may have broader effects |
| [token-savior](https://github.com/Mibayy/token-savior) | Mixed | Token-efficient navigation/memory/output | Experimental; confirm agent actually calls it |
| [jcodemunch-mcp](https://github.com/jgravelle/jcodemunch-mcp) | Symbol retrieval | Retrieve small functions instead of files | Commercial licensing conditions may matter |
| [toktoken](https://github.com/mauriziofonte/toktoken) | Symbol retrieval | Fast ctags-driven lookup | Verify current Universal Ctags prerequisites |
| [tokensave](https://github.com/aovestdipaperino/tokensave) | Mixed | Broader analysis + retrieval | Multiple responsibilities, overlapping indexes |
| [codemap](https://github.com/jordancoin/codemap) | Lightweight map | Cheap project structure and dependency overview | May duplicate native search features |
| [sprout](https://github.com/Sprout-DevLabs/sprout) | Lightweight map | Compact guided project orientation | Verify language coverage, freshness, useful retrieval |
| [RepoMapper](https://github.com/pdavis68/RepoMapper) | Repository map | Aider-like tree/symbol map | Similar to maps agents may already have |
| [repomix](https://github.com/yamadashy/repomix) | Context export | One-time selective repository packaging | Full snapshots repeated in every chat can be costly |
| [aider](https://github.com/Aider-AI/aider) | Coding agent | A second coding workflow with token-budgeted mapping | Primarily alternative agent, not just a Claude/Cursor plugin |
| [RTK](https://github.com/rtk-ai/rtk) | Output compression | Reduce noisy build/test/git terminal text | Full session savings may be far below per-command savings |
| [Headroom](https://github.com/headroomlabs-ai/headroom) | Output compression | Reduce repetitive JSON / logs / tool responses | Compression quality and workload mix determine value |
| [agent-browser](https://github.com/vercel-labs/agent-browser) | Browser specialist | Make UI validation/failure discovery more efficient | Useful only when browser interaction is actually needed |
| [claude-mem](https://github.com/thedotmack/claude-mem) | Automatic memory | Resume prior work without re-discovery | Observer/context overhead and native memory duplication |
| [caveman](https://github.com/JuliusBrussee/caveman) | Output compression | Compact proxy/skill outputs | Needs rigorous head-to-head measurement |

## Recommended *experimental* pairings

| Workload | Baseline | Candidate pilot | Do not automatically combine with |
|---|---|---|---|
| New or tiny repo | Native search + short instructions | Usually none | Every code graph / auto memory process |
| Small/medium repo with repeated exploration | Native search | Sprout **or** codemap | Multiple mapper tools |
| Large monorepo, frequent dependency changes | Native search | code-review-graph **or** codebase-memory-mcp | Another overlapping graph |
| Complex architecture, repeated decisions | Native docs | Trail-Code | Separate graph + automatic memory until benchmarked |
| Tool-output-heavy backend | Raw terminal output | RTK **or** Headroom | Multiple simultaneous compressors |
| Browser-heavy product engineering | Existing browser workflow | agent-browser | Unnecessary app-wide graph additions |
| One-off deep context sharing | Targeted source selection | repomix | Full repo export on every agent turn |

## Research-confidence policy

- **Verified project fact:** inspected current code/docs for a specific version. Include version and URL.
- **Author claim:** numbers in the repository README or author benchmarks. Label as such; never equate operation-level compression with billing reductions.
- **Independent user report:** useful indication, but distinguish workload, author affiliation, sample size, model, and task acceptance criteria.
- **Our hypothesis:** recommendation that needs a controlled benchmark, not a promised effect.
- **Measured RepoMoor result:** only when we publish reproducible scripts, task fixtures, logs and outcome grading. **No such measured token-saving result is claimed in v0.1.0.**

## Hard questions before adding a tool

1. Does the current agent already have an equivalent built-in index, search, memory, or browser capability?
2. What fraction of a full session's billed tokens or time are consumed by *this tool's* target problem?
3. Does the indexed graph cover dynamic languages, generated code, runtime registration, and test/dependency edges?
4. Is indexing local and incremental? What disk/RAM/CPU resources does it use, and how stale can it get?
5. Will Claude Code/Cursor actually call the tool, or keep using built-in grep/read operations?
6. Will installation touch `~/.claude`, user preferences, global MCP settings, shell profile, or shared hooks?
7. Can the user legally use it for commercial development under its **current** license?
8. Can we uninstall without damaging or mutating pre-existing settings?
9. Does full-task correctness stay at least as high as the baseline?

## Sources

Upstream repositories linked in the table. Native agent configuration evidence: [Claude guidance](https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts), [Claude context steering](https://claude.com/resources/articles/steering-claude-code-skills-hooks-rules-subagents-and-more), [Cursor project rules](https://prod.cursor.com/docs/rules), [Cursor ignore files](https://prod.cursor.com/help/customization/ignore-files). See [reference links](SOURCES.md).
