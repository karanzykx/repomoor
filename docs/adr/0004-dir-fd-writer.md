# ADR 0004: Race-safe create-only writer via directory file descriptors

**Status:** accepted | **Date:** 2026-11-23

## Context

`safe_create` used to check each ancestor of the target for symlinks, then open the full path. Between the check and the open, another process could replace a checked directory with a symlink; `O_NOFOLLOW` only protects the last path component, so the write could land outside the project. A deterministic test reproduced this: swapping `.repomoor` for a symlink just before the final open made the old writer create the file in the outside directory. Separately, the containment check compared paths as text, so a relative path containing `..` passed it.

## Decision

- Validate every relative path as text first: no absolute paths, drives, `..`, `.`, empty parts, backslashes or NUL bytes.
- On platforms with `dir_fd` support plus `O_NOFOLLOW` and `O_DIRECTORY` (Linux, macOS, BSDs), open the root, then each directory relative to the previous open descriptor with `O_DIRECTORY | O_NOFOLLOW`. Create missing directories with `mkdir(dir_fd=...)`, and create the file with `O_CREAT | O_EXCL | O_NOFOLLOW` relative to its parent descriptor. Nothing is resolved again by path after it has been opened.
- Existing leaves are inspected through `O_NOFOLLOW | O_NONBLOCK`, so a symlink is refused and a FIFO cannot block.
- If a write fails partway, remove the file only when its device and inode still match the one this call created.
- Platforms without `dir_fd` (notably Windows) keep the check-then-open path walk, with the same text validation. It is documented as not race-free.

## Consequences

On POSIX, a concurrent symlink swap can make a write fail or land in the directory that was actually opened (which may have been renamed within the project), but it cannot redirect the write outside the root. Windows remains best-effort until a junction-aware design and a Windows CI job exist (backlog P0-04). Error statuses keep their v0.2 wording, so callers and reports are unchanged.
