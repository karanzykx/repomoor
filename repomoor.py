#!/usr/bin/env python3
"""Zero-install launcher: python3 repomoor.py /path/to/repo."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from repomoor.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
