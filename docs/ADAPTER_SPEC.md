# Safe tool adapter specification (RFC-001)

**Status: proposal only, NOT implemented.** RepoMoor currently advises on third-party tools but does not invoke their installers or automatically configure MCP or hooks.

## Why adapters?

Each tool installs differently and can have surprising side effects. A project-local advisor must not blindly run arbitrary install commands, especially scripts that write user-level Claude/Cursor configuration. An adapter would describe *precisely* what a project-specific integration would change, and refuse it if isolation cannot be guaranteed.

## Proposed adapter contract

```json
{
  "schema_version": 1,
  "name": "example-graph-tool",
  "upstream": "https://github.com/example/tool",
  "version": "PINNED_RELEASE_OR_COMMIT",
  "capabilities": ["code-graph", "mcp"],
  "requirements": ["a supported runtime installed by the user"],
  "supports_project_only": false,
  "network_access": "unknown",
  "may_run_hooks": true,
  "reads_sensitive_data": "unknown",
  "allowed_repo_paths": [".mcp.json", ".repomoor/integrations/example-graph-tool/"],
  "conflicts_with": ["other-code-graph"],
  "install_plan": [],
  "checks": [],
  "rollback_plan": [],
  "requires_manual_approval": true
}
```

This is an **illustrative target schema**, not a working file format or executable plugin. Unknown effects default to **cannot auto-install**.

## Required phases

1. **Discover:** read only project-scoped evidence of existing integration and mark each fact as `observed`, `inferred`, or `unknown`.
2. **Plan:** propose a deterministic list of file creates/edits and required subprocesses, plus exact expected external effects. Flag conflicts with existing files and overlapping tools.
3. **Dry-run:** validate all paths within the explicitly selected project, display a complete diff and full subprocess command list, and check requested network access. No changes.
4. **Approve:** require explicit interaction for each category of side effect (file writes, code execution, network). No broad confirmation that hides shell commands.
5. **Apply:** use a transaction journal. Create a backup *only for files the tool owns or that the user explicitly grants permission to edit*; never silently replace user-owned instructions.
6. **Verify:** test the adapter's project-local operation with bounded diagnostics, without leaking tokens or secrets.
7. **Undo:** remove only adapter-owned resources verified by the journal; never remove unknown files.
8. **Reassess:** use end-to-end benchmark evidence, not just whether the service starts.

## Conflict handling

- Existing `AGENTS.md`/`CLAUDE.md`: ask user to edit/link manually; default skip.
- Existing `.mcp.json`: do not rewrite or merge in v1 adapter proposals; offer a manual snippet instead.
- Existing hooks: never add another hook by default. Explain precedence and cost before proposing any additive behavior.
- Existing graph/index: do not suggest a second one without a specific A/B plan.
- Project is a monorepo: distinguish root-level integration from per-service indexing; don't make speculative cross-service assumptions.
- Incompatible license: block automated integration rather than assume permissive rights.

## Candidate adapter order

1. RTK *read-only compatibility analyzer*: see whether current shell output is large and local integration is feasible.
2. Trail-Code *project-only plan preview*: inspect exact documented effects, test no-global flags and rollback.
3. code-review-graph *graph plan preview*: language support and index freshness controls.
4. Agent-browser *specialist plan preview*: browser permissions, downloaded binaries and sandbox concerns.

## Review test matrix

- Blank project and read-only checkout.
- Project with existing Claude, Cursor, AGENTS, and MCP settings.
- Multiple nested services, conflicting tool names.
- Filename with Unicode/whitespace, symlinked directories, output collisions, interrupted install.
- No network, unsupported platform, missing package runtime, commercial license unknown.
- Invariant that no home/global path changes in a disposable controlled test environment.

**Exit condition:** No adapter moves out of suggestion-only until the team has run and published this matrix against a pinned upstream version.
