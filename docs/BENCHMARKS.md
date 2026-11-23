# Benchmark plan: measure completed tasks, not just token snippets

**Status:** specification. No real-model A/B savings are claimed in this repository's alpha.

## Why a benchmark is necessary

Tools may remove 90% of tokens from a *single* code lookup while adding setup prompts, MCP schema overhead, extra calls, fallback searches, and more retries. Cached input and subscription usage limits also change perceived cost. Compare full, correctly completed tasks, not just isolated retrieval calls.

## Experimental design

- Use real repositories with known history and reproducible failing tests; seek permission for any proprietary code.
- For each repository, select 6 to 10 tasks covering navigation, code modification, blast-radius analysis, cross-service edits, error-log investigation, and memory resumption (when supported).
- Conditions: **A** native Claude Code or Cursor with the project's existing native instructions; **B** exact same environment plus **one** candidate tool. Never combine multiple pilots initially.
- Match model/version/effort, agent settings, prompt text, permission level, machine resources, repo commit, allowed network access and context-history state.
- Use clean Git worktrees and fresh context; randomize order between A and B and replicate runs (3+ per condition when practical).
- Before B runs, record index warm-up time, disk and memory footprint. Distinguish warm-cache and cold-cache scenarios.
- Verify the candidate tool is invoked; if never used, conclude that integration failed *for this setup*, rather than declaring a savings result.
- Grade results against independently defined tests / acceptance criteria, plus manual inspection for missing dependencies or invented edits.

## Recommended task fixtures

| Task | Primary metric | Failure mode to catch |
|---|---|---|
| Find implementation of a feature | Time + source files retrieved | Agent confidently points to wrong module |
| List callers of a changed API | Dependency recall / precision | Missed dynamic or cross-service caller |
| Fix known regression | Tests pass + patch quality | Compression hides a stack trace |
| Cross-service feature modification | Acceptance tests + omissions | Agent only edits first service |
| Refactor shared component | CI / relevant tests | Missed usage from stale index |
| Resume documented decision | Correct design reuse | Memory returns outdated guidance |
| Diagnose a failing build | Root-cause rate / time | Log compressor discards needed error lines |
| Browser UI acceptance check | Correct observed browser state | Unreliable navigation and overused snapshots |

## Metrics to capture

1. **Correctness:** task accepted (binary + rubric), passing tests, dependency recall, diff review.
2. **Full-session usage:** billed uncached input, cache-write input, cache-read input, output tokens, tool call count, per-tool time. Prefer provider usage exports to manual estimates.
3. **Cost:** apply the correct billing plan's price/allowance model; subscription plan usage is *not* direct API dollar cost.
4. **Latency:** start-to-verified-result, not start-to-first-patch.
5. **Overhead:** indexing/build time, disk, RAM, tool token schemas, prompts, and repeated/failed searches.
6. **Reproducibility:** agent version, repo commit, candidate version, task ID, model version, OS, clean/warm cache state.

## Core success metric

```text
cost_per_correct_task = sum(billed_cost_per_attempt) / number_of_accepted_tasks
```

Also report the full table of acceptance rates, medians, variance, and confidence intervals. If two candidates have different task completion rates, don't compare token usage only on their *successful* subset without also explaining the selection bias.

## Adoption threshold (proposal)

A practical initial target is ≥10% improvement in cost per correctly completed task, without worse task correctness or meaningful maintenance burden. This is a target set by RepoMoor, not an external benchmark result.

## Result table template

| Repo/task | Agent/model | Condition | Success? | Input tokens | Cached tokens | Output tokens | $ / units | Runtime | Tool invoked? | Notes |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| sample/navigation | record version | baseline | pending | - | - | - | - | - | N/A | - |
| sample/navigation | same version | candidate | pending | - | - | - | - | - | pending | - |

Keep your experiment ledger outside the repository if it holds private data. Do not record secrets, source code, or proprietary prompts without authorization.
