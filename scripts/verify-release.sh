#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
python3 -m unittest discover -s tests -v
python3 repomoor.py --catalog --json >/dev/null
python3 repomoor.py examples/sample-monorepo --json >/dev/null
python3 repomoor.py examples/sample-monorepo --doctor --json >/dev/null
printf '\nRepoMoor verification passed.\n'
