# Operator guide

## Requirements

Python 3.10+ with a usable terminal. The bundled launcher uses only the Python standard library; there is no network requirement, key, MCP installation, or project package installation.

## Commands

```bash
python3 repomoor.py --help
python3 repomoor.py /path/to/project
python3 repomoor.py /path/to/project --non-interactive
python3 repomoor.py /path/to/project --json
python3 repomoor.py /path/to/project --apply
python3 repomoor.py /path/to/project --apply --integrate
python3 repomoor.py /path/to/project --doctor
python3 repomoor.py /path/to/project --doctor --json
python3 repomoor.py --catalog
python3 repomoor.py --catalog --json
python3 repomoor.py /path/to/project --max-files 20000 --max-depth 8 --max-dirs 10000
```

`--json` outputs a valid JSON document and uses non-interactive defaults. There is no interactive selection when stdout is not attached to a terminal. Options use numbered entries in interactive mode. If you accept defaults on a blank repo, RepoMoor will *not* install graph/index tools.


## Answers file

`--answers FILE` gives the questionnaire answers up front, so runs are repeatable:

```bash
python3 repomoor.py /path/to/project --answers examples/answers.example.json --json
```

Rules (any violation exits with code 2 before scanning or writing, and the error never echoes file values):

- A regular file of at most 16 KiB, UTF-8 JSON, holding one object.
- Optional `"repomoor_answers_version": 1`; any other version is refused.
- Allowed keys and choices:
  - `agents`: `both`, `claude`, `cursor`, `other`
  - `priority`: `balanced`, `tokens`, `correctness`, `speed`
  - `pain`: `unknown`, `rediscovery`, `impact`, `terminal`, `browser`
  - `future_project` (blank repos only): `unknown`, `web`, `backend`, `multi`, `library`
  - `scope` (only when service folders are seen without a workspace file): `unsure`, `yes`, `no`
- Omitted keys are asked interactively, or take the default when there is no terminal.
- A key the scan already decides is reported as `not-applicable` and not used.
- Cannot be combined with `--doctor`. The file may live outside the project; RepoMoor only reads it.

## Preview and apply

The default is non-mutating. `--apply` creates `.repomoor/` reports only if each target file is missing. `--apply --integrate` can create new agent instruction files only when none of the supported existing rule locations exist. Manual agent integration is appropriate when your repository already defines local rules. On reruns, a `PRESERVED` result means your prior file was not updated; this is deliberate.

## Typical output

```text
=== Recommendation preview ===
Project: /work/my-project
Sampled source files: 104
Architecture: small-or-early-stage
Foundation / pilots:
  + Native project context + curated architecture decisions
Optional:
  ? Sprout or codemap [MAP_LIGHTWEIGHT]: ...
Preview complete. Nothing changed.
```

Exact output depends on the actual project and your answers. Reports are meant to be *read and verified*, not asserted as ground truth about runtime architecture.

## Understanding the generated profile

- `scan`: cheap observable facts, bounded by file/depth budgets.
- `signals`: interpretation of manifests and project-local config; can be inaccurate.
- `answers`: selected preferences, not automatically inferred from code.
- `plan.*[].code` / `plan.*[].evidence`: why each tool was recommended, offered or skipped. Codes are listed in [ARCHITECTURE.md](ARCHITECTURE.md#reason-codes-and-evidence); skipped items with codes are in `plan.skipped_details`.
- `scan.truncation_reasons`: which limits stopped the scan (`max_files`, `max_dirs`, `max_dir_entries`). Empty means the scan was complete within `--max-depth`. `scan.dirs_unreadable` counts folders that could not be listed.
- `signals.instruction_files`: existing agent instructions as `{path, scope, description}`, where `scope` is `root` or `nested`. Any entry blocks `--integrate`, and they are listed in `PROJECT_CONTEXT.md` as taking precedence. `scan.nested_rule_paths` is the raw list found by the scan (capped at 200; `max_nested_rules` appears in `truncation_reasons` if it overflows).
- `signals.parse_issues`: project files that were skipped or could not be parsed, as `{path, code}`. Codes: `too-large` (over 192 KiB), `too-deep` (JSON nested over 64 levels), `invalid-json`, `not-object`, `not-regular-file` (for example a symlink), `unreadable`. Signals that would have come from these files are missing; `--doctor` warns about them.
- `answer_sources`: where each answer came from: `file`, `interactive`, `default`, `inferred` (decided by the scan), or `not-applicable` (given in the answers file but overridden by the scan).
- `recommendation`: transparent rules based on those signals and preferences.
- `no_installation_performed`: should always be true in the alpha.

## Existing configurations and fallback

If a project references a known graph/index integration, RepoMoor recommends confirming whether it works before adding another. It **does not** probe the project's global tools, and does **not** claim a server is installed or healthy merely because it appears in config. If existing root/scoped agent instructions exist, RepoMoor leaves them alone, including under `--integrate`. It never edits `.mcp.json`, `.claude/settings.json`, or `.cursor/mcp.json`.

## Updating old reports

Run `--doctor` first. If it reports stale source-language counts or manifest paths, inspect your `.repomoor/` files. If you want a fresh snapshot, archive the old generated folder outside the target or delete only the files you intentionally want regenerated, then run `--apply` again. **There is intentionally no destructive `--force` flag.**

## Private repository considerations

Generated files include paths and filenames, sometimes identifying internal architectures or products. RepoMoor never modifies the target's `.gitignore`; **do not assume `.repomoor/` is ignored in every repository**. Review generated artifacts before committing or sharing them. Avoid pasting any sensitive project info into a public issue.

## Troubleshooting

- **No questions:** Run interactively without `--json`/`--non-interactive` and with a terminal attached.
- **Project path missing:** Pass an existing directory, or create the blank directory before running.
- **Preview feels generic:** It is intentionally conservative, especially for empty repos; adjust questions and rerun after code exists.
- **Existing files not updated:** This is expected. Check `PRESERVED` outcomes and follow the manual refresh process.
- **Expected MCP tool not detected:** Only local known markers and bounded config paths are checked; global tools are intentionally invisible.
- **Read-only checkout:** Use preview or doctor. `--apply` will return file-creation errors without replacing anything.
- **Symlink refusal:** Use a real directory inside the target repo rather than a symlinked `.repomoor` path.
