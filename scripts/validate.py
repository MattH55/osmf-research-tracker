#!/usr/bin/env python3
"""CI entry point for PAIS cohort and estimate-layer validation."""
from subprocess import run
from sys import executable
from pathlib import Path
root=Path(__file__).resolve().parents[1]
run([executable, str(root/'scripts'/'build_pais_cohorts.py'), '--check'], check=True)
run([executable, str(root/'scripts'/'build_estimates.py'), '--check', *(['--strict'] if '--strict' in __import__('sys').argv else [])], check=True)
