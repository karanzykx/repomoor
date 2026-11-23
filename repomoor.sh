#!/usr/bin/env sh
# Shell launcher; does not install anything or change the user's environment.
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/repomoor.py" "$@"
