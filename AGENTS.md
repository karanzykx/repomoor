# Repository instructions for coding agents

RepoMoor is a safety-first, project-local CLI. Read `docs/ARCHITECTURE.md`,
`docs/SAFETY.md`, and `docs/PRODUCT_SPEC.md` before altering its behavior.

- Never add a default operation that writes outside the explicitly selected project root.
- Never run external tool installers, `npx`, curl-to-shell, hooks, or package managers as part of analysis.
- Never overwrite an existing user file; guard parent symlinks and use exclusive creation.
- Treat repo manifests and agent configuration as untrusted inputs; never execute or print secrets from them.
- Keep current functionality standard-library-only; optional dependencies must be explicit.
- Add regression tests for every new config format, filesystem case, or adapter.
- Maintain the tool catalog and docs when recommendations change.
- `python3 -m unittest discover -s tests -v` is the test command.
- If `tests/test_golden.py` fails after an intended output change, regenerate with `REPOMOOR_UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden` and review the `tests/golden/` diff; never regenerate to hide an unexplained change.
- Claims about savings must be labeled either measured independently, author-reported, or hypothetical.
