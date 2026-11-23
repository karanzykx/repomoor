# Safety and threat model

## Non-negotiable boundaries

**RepoMoor is an advisor, not an installer.** It must not run project scripts, shell commands embedded in manifests, hooks, MCP binaries, package managers, or AI tools during analysis. It must not inspect the home directory or machine-wide configuration to discover globally installed tools. It must not write outside the requested repository and must not modify existing files without a new explicit, reviewed mechanism (not available in v0.1.0).

## Threats and mitigations

| Threat | Current defense | Remaining limitation |
|---|---|---|
| Malicious `package.json` scripts | Parse bounded content; never execute | Malformed input may affect detection quality |
| Oversized, deeply nested or malformed manifests | 192 KiB read limit; JSON nesting limited to 64 levels before parsing (deep nesting used to crash with `RecursionError`); problems reported as `signals.parse_issues` path + code, never content | Skipped files mean missing signals; check `--doctor` |
| Regex denial of service | Patterns avoid newline-spanning repetition; the `Cargo.toml` check went from 51.6 s to milliseconds on a 190k-blank-line file | Keyword patterns are escaped literals; new patterns need a timing test |
| Huge directory trees or folders | `--max-files`, `--max-depth`, `--max-dirs` (default 6000) and a 20,000-entry cap per listing; `scan.truncation_reasons` says which limit hit | Very deep `--max-depth` with a high `--max-dirs` can still be slow on network filesystems |
| Manifest contains secrets | Only serialize narrow derived signals | Config is still read in process memory; memory/debuggers are outside this guarantee |
| Child directory symlink escapes repo | Skip symlinks in walk and reads | User can explicitly choose a root path that resolves through a symlink |
| Symlinked report folder | Refuse to write through symlinked path segments | On POSIX, closed by directory-fd traversal (ADR-0004). On Windows the fallback path walk still has a check-then-open window |
| Directory swapped for a symlink mid-write | POSIX: each part opened relative to the already-open parent with `O_NOFOLLOW`; regression tests swap a directory deterministically and under thread churn | Windows fallback is not race-free; junctions are untested (P0-04) |
| Relative path with `..` or an absolute path | Checked as text before any filesystem access; refused | None known |
| Existing user instructions overwritten | Exclusive create-only writes; detect existing rules | New file may still change behavior if user opts into `--integrate` |
| Tool adapters perform global installation | No third-party adapters or installs in current release | Future adapters require explicit policy + verification |
| Misleading graph/integration detection | Clearly label as config hints, not live capability | Keywords can be incomplete or false positives |
| Prompt injection in source/README | No LLM interaction with scanned text | Markdown output may include unusual filenames; don't treat it as trusted instructions |
| Exfiltration by tool | No network calls in core CLI | Future networked benchmark runners must opt in separately |

## Filesystem hardening details

`safe_create` (in `src/repomoor/fs.py`, the only module allowed to write) works like this:

1. **Text check of the path.** Absolute paths, drive letters, `..`, `.`, empty parts, backslashes and NUL bytes are refused before the filesystem is touched.
2. **POSIX: directory-fd traversal** ([ADR-0004](adr/0004-dir-fd-writer.md)). The root and then each directory are opened relative to the previous open descriptor with `O_DIRECTORY | O_NOFOLLOW`. Missing directories are created with `mkdir(dir_fd=...)`, and the file with `O_CREAT | O_EXCL | O_NOFOLLOW` relative to its parent descriptor. A directory swapped for a symlink mid-call makes the write fail, or land in the directory that was actually opened, but never outside the root.
3. **Existing leaf.** Inspected with `O_NOFOLLOW | O_NONBLOCK`: a symlink is refused, a FIFO or directory is preserved without blocking, and a regular file is compared byte for byte (`UNCHANGED`/`PRESERVED`). It is never overwritten.
4. **Failed write.** The partial file is removed only if its device and inode still match the file this call created.
5. **Windows / no `dir_fd`.** A check-then-open path walk with the same text validation. This is **not** race-free; avoid running it on a directory another process is changing.

Still not covered: a lock or rollback journal for multi-file writes (P3-06), Windows junction semantics (P0-04), and the read side. `safe_read` still checks then reads by path, but it only feeds keyword matching and never echoes content.

## Data collected / transmitted

No telemetry or outbound connections are present in the core. The generated profile contains project filenames/manifest paths, language counts, project-local config **names**, user answers, selected recommendations, and the local absolute target path. It does not intentionally contain source file bodies or MCP credential values. Profiles can still expose sensitive **repository structure**; review them before uploading publicly. The project's `.gitignore` excludes its own `.repomoor` output, but RepoMoor does not alter a target project's `.gitignore`.

## Existing configurations

Do not attempt to merge `CLAUDE.md`, `AGENTS.md`, `.cursor/rules`, MCP JSON, hooks, or agent settings automatically. In the alpha, detecting any known agent rules prevents integration entirely. The user may manually link the generated context after review.

`--integrate` writes nothing when any of these hold:

- **A known root instruction location exists.** Examples: `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md`, `.claude/CLAUDE.md`, `.claude/{rules,skills,commands,agents}`, `.cursorrules`, `.cursor/rules`, `.github/copilot-instructions.md`, `.github/{instructions,prompts}`, `.windsurfrules`, `.windsurf/rules`, `.clinerules`, `.roorules`, `.roo/rules`, `.continue/rules`, `.junie/guidelines.md`, `.kiro/steering`, `GEMINI.md`. The full list is `scanner.INSTRUCTION_PATHS`.
- **A nested instruction file is found during the scan.** That means `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md` or `GEMINI.md` in any subfolder, or a nested `.cursor/rules` folder. Names are matched case-insensitively, so the result is the same on every filesystem. Folders the scan skips (`node_modules`, `vendor`, `.git`, …) do not count.
- **The scan was truncated.** Nested rules can then not be ruled out, so integration is skipped rather than guessed.

MCP and settings files (`.mcp.json`, `.claude/settings.json`, `.gemini/`, `.aider.conf.yml`) are detected and reported but are not instructions, so they don't block integration on their own. Only project-local paths are checked; no user or global configuration is read. `RulePreservationTests` runs every location above through every `agents` answer and checks that no pre-existing byte changes. Keeping their existing configuration authoritative is more important than forcing integration.

## Third-party tool risk review (future)

Each prospective adapter must report: canonical repo URL, exact version/commit, license applicability, local-only guarantee, network access, subprocess commands, hooks, files to create, config conflicts, data retention, resource overhead, dry-run results, rollback plan. An adapter must remain suggestion-only if any of these are unknown or if upstream cannot prove project-local behavior.

## Reporting vulnerabilities

See root `SECURITY.md`. Please don't include actual project credentials or internal repository paths in public issues.
