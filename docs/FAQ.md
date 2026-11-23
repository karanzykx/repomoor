# Frequently asked questions

## Will RepoMoor automatically install all 19 tools?

No. That would create overlapping integrations, hidden dependencies and potentially non-local configuration effects. The alpha recommends a minimal subset and intentionally stops before any third-party installation. Adapter planning is future work.

## Does it lower AI token usage by itself?

The CLI itself does not change how Claude Code or Cursor consumes tokens unless you opt into creating and using a lightweight agent instruction. The principal current value is an explainable plan and project notes; any actual savings must be measured through a controlled task evaluation.

## Does it check global Claude Code, Cursor or MCP installations?

No. That restriction is part of the project specification. It looks at known files under the explicitly selected project root only. An MCP name appearing in project config is not proof the binary works.

## Will it change my existing `CLAUDE.md`, `AGENTS.md` or Cursor rules?

No. RepoMoor never overwrites existing files. `--integrate` is disabled if known project agent rules already exist, and there is no automatic merge. It does not modify MCP config or hooks.

## What happens if the generated report is old?

`--doctor` can identify changes in sampled language counts or detected manifest paths; it cannot detect every semantic source change. The project owner must explicitly archive/delete old generated files to allow recreation, because RepoMoor intentionally has no force-overwrite mode.

## Why not automatically generate an index for every project?

Small and early projects often work well with built-in search. Graph build and maintenance, MCP prompt overhead and incorrect graph coverage may outweigh savings. Pilot one tool only after a repeatable task bottleneck appears.

## Why Python rather than pure Bash?

Python's standard library offers cross-platform JSON, filesystem traversal, argument parsing, and test tooling without invoking external commands. The POSIX `.sh` wrapper is included for convenience, while Windows can call `repomoor.py` directly.

## Is it safe for confidential work?

There are no network calls or telemetry in the core. The scan nevertheless processes project filenames and bounded local manifests/config, and generated profiles reveal some repository structure. Review reports before committing or uploading. The program is not a security sandbox against malicious concurrent filesystem modification. See [safety](SAFETY.md).

## Do I need to install Python dependencies?

No for `python3 repomoor.py`. Optional installation as a Python package uses `pip` and is outside RepoMoor's own operations.

## Why is `AGENTS.md` selected for both agents?

Current Claude Code and Cursor documentation supports shared project instructions. Creating both `AGENTS.md` and `CLAUDE.md` with identical text would risk duplicate always-loaded context. If an existing rules system is detected, RepoMoor creates neither. Agent behavior can change, so confirm on your installed versions.
