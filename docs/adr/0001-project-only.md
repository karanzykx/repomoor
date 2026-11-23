# ADR 0001: Project-only discovery and writes

**Status:** accepted | **Date:** 2026-11-18

## Context

The user explicitly wants a bootstrapper usable across unrelated projects with no effects on personal or other project environments. Agent global settings, home directories and hooks create high cross-project risk.

## Decision

The CLI will inspect only the explicitly selected repository root, avoid following child symlinks, and never probe installed global tools. Default is read-only; explicit `--apply` creates only new files under that project. Existing files are not replaced. Runtime configuration references are treated as hints, not proof of installation.

## Consequences

Fewer false side effects and easier review. The tool cannot answer whether some globally installed CLI or MCP server exists; this is an intentional limitation, not a bug. Future project-only installation requires a policy-checked adapter design with further filesystem hardening.
