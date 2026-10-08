#!/usr/bin/env python3
"""CI entry point for Genetic Correlates Explorer data validation."""
from pathlib import Path
from subprocess import run
from sys import executable

root = Path(__file__).resolve().parents[1]
run([executable, "-m", "genetics_pipeline.main", "--skip-live", "--check"], check=True, cwd=root)
