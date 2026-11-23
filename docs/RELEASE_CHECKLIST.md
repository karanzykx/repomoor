# GitHub release checklist

## Before the first push

- [ ] Check if `repomoor` is available as a GitHub repository slug and if branding/trademark conflicts exist. Search results are not a legal clearance.
- [ ] Choose GitHub owner/organization; add a maintainer contact for security reports if desired.
- [ ] Review MIT license copyright attribution; you may adjust it before first publication.
- [ ] Confirm the README descriptions, commands and feature statuses match the code.
- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Run `python3 repomoor.py --catalog --json` and verify 19 entries.
- [ ] Test `--json`, `--apply`, `--apply --integrate` and `--doctor` against throwaway directories.
- [ ] Inspect the ZIP contents and exclude generated `.repomoor/`, secrets, local `.env` files and cache files.
- [ ] Review external links, licensing language and disclaimer that other tools are not bundled.

## Suggested Git commands

```bash
# Extract RepoMoor ZIP and cd into the repomoor directory.
git init
git branch -M main
git add .
git commit -m "feat: initial RepoMoor alpha release"

# Create the blank repo on GitHub, then substitute your actual URL:
git remote add origin https://github.com/YOUR-ACCOUNT/repomoor.git
git push -u origin main
```

Do not copy the placeholder URL without replacing `YOUR-ACCOUNT`. If GitHub creates a README or license first, resolve that existing history intentionally rather than force pushing.

## After publishing

- [ ] Replace the README's optional placeholder badges with real GitHub Actions URLs, if desired.
- [ ] Enable repository security advisory intake and set contact details.
- [ ] Create labeled issues from `docs/ROADMAP.md`; assign priority labels.
- [ ] Enable GitHub Actions; verify CI on Python 3.10 through 3.13.
- [ ] Add a proper alpha release tag, e.g. `v0.1.0`, with changelog notes.
- [ ] Ask for usability feedback from blank, single-service and monorepo users.
- [ ] Do not publish performance savings without reproduced task-level evidence.
