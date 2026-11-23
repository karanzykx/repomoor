# Changelog

All notable changes are recorded here. RepoMoor is pre-1.0, so behaviour and output can change between minor versions.

## [0.1.0] - 2026-11-24

First public preview.

- Scans a blank or existing repository by file names and bounded manifest reads. It never runs project code, never reads global or user settings and never follows symlinks.
- Asks a few numbered questions, or reads them from `--answers FILE` for repeatable runs. Every answer records where it came from.
- Recommends a minimal AI coding setup. Each recommended, optional or skipped tool has a stable reason code and the evidence that triggered it.
- Detects existing agent rules and settings, at the root and in subfolders, for Claude Code, Cursor, Copilot, Windsurf, Cline, Roo Code, Continue, Gemini CLI, Junie and Kiro.
- `--apply` creates report files in `.repomoor/` and never overwrites anything. `--integrate` adds a minimal `AGENTS.md` or `CLAUDE.md` only when no rules exist anywhere in the project.
- `--doctor` is a read-only health check; `--catalog` lists the 19 researched tools; `--json` prints machine-readable output.
- File writes walk the path with directory file descriptors on Linux and macOS, so a folder swapped for a symlink cannot redirect a write. Windows uses a simpler fallback.
- Oversized, deeply nested or malformed manifests are reported instead of crashing the scan, and directory walking has limits (`--max-files`, `--max-depth`, `--max-dirs`).
- Standard library only. Python 3.10 or newer.
