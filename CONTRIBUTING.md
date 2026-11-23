# Contributing to RepoMoor

Thanks for helping create a reliable, minimal-dependency AI development bootstrapper. The best contributions are small, testable improvements to project discovery, correctness, and safety.

## Start here

1. Read `docs/PRODUCT_SPEC.md`, `docs/ARCHITECTURE.md` and `docs/SAFETY.md`.
2. Pick an item from `docs/ROADMAP.md`, or open an issue describing the problem and its acceptance criteria.
3. Run `python3 -m unittest discover -s tests -v` before and after changes.
4. Keep all preview and doctor paths side-effect-free; do not add auto-installs or global config probes.
5. Include tests on a synthetic/throwaway repository for any filesystem or config change.
6. Document what is inferred and what is verified. Never advertise unmeasured token savings.

## Local development

```bash
python3 repomoor.py examples/sample-monorepo --json
python3 repomoor.py examples/sample-monorepo --doctor
python3 repomoor.py --catalog
python3 -m unittest discover -s tests -v
```

No dependencies need to be installed for the commands above. Optional editable installation is described in the README.

### Golden-output tests

`tests/test_golden.py` runs every command mode against fixed fixture repos and compares all user-visible output with `tests/golden/*.json`: preview text, JSON, doctor checks, error messages and the files `--apply` writes. A failure prints a diff of what changed.

If the change is intended, regenerate the goldens, then **read the diff of `tests/golden/`** before committing it. The diff is the review of your behaviour change:

```bash
REPOMOOR_UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden
```

Never regenerate just to make a failure go away without reading the diff. To cover a new case, add a fixture to `FIXTURES` or a run to `RUNS` in `tests/test_golden.py` and regenerate.

## Coding standards

- Python 3.10+; standard library only in the default runtime.
- Keep deterministic, explainable recommendation behavior.
- Avoid reading file bodies except when explicitly needed for bounded manifests/config metadata.
- Avoid storing sensitive contents from scanned projects in generated profiles.
- Use exclusive create-only writes and treat path/symlink handling as security-critical.
- Keep clear limits on source-file scanning and mention when results are truncated.
- Update both `docs/TOOL_CATALOG.md` and the bundled `tools.json` when adding/revising a candidate.
- Follow `AGENTS.md` for development-agent instructions.

## Pull request checklist

- [ ] Tests added or updated for behavior changed.
- [ ] No new filesystem/global side effect in default/doctor/catalog modes.
- [ ] Existing-file behavior remains non-destructive.
- [ ] CLI help, README, docs and changelog are updated if appropriate.
- [ ] Claims are sourced and differentiated from hypotheses.
- [ ] Private paths, credentials or proprietary repository data are absent from commits and fixtures.

## License of contributions

By opening a pull request, you confirm that the contribution is your own work (or that you have the right to submit it) and you agree that it is licensed under the project's [MIT License](LICENSE). Do not submit code copied from projects with incompatible licenses.

## Policy for third-party adapters

PRs proposing active installation are out of scope until `docs/ADAPTER_SPEC.md` security gates are implemented. A proposal-only adapter spec or test harness is welcome.
