# ADR 0003: Optimize correctly completed tasks

**Status:** accepted | **Date:** 2026-11-18

## Context

A high per-operation token compression percentage can be meaningless if the tool adds schemas, extra lookups, incorrect code changes, rework, or user-facing latency. Subscription usage limits also differ from billed API token counts.

## Decision

Use **cost and time per correctly completed task**, correctness and dependency coverage as primary metrics. Track full-session input/output/cache tokens and tool invocation rate; distinguish author and independent data. Do not claim actual token savings until reproducible evaluations exist.

## Consequences

A tool that appears extremely efficient on a `grep` alternative may legitimately be rejected. Research takes longer, but recommendations are more defensible.
