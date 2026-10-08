"""CLI entrypoint: python -m genetics_pipeline.main [--skip-live] [--check]

Runs, in order:
  0. connectivity check (module 4's "fail loudly on 410/404" rule, applied
     at the top of the run rather than per-module)
  1. registry: live EFO/MONDO term-currency check
  2. validate: schema + cross-reference validation (local)
  3. grading + matrix (module 6, local)
  4. site build (module 7, local) -> genetics/ + genetics/data/*.json

--skip-live skips steps 0-1 (no network calls) for offline iteration.
"""
from __future__ import annotations

import argparse
import sys

from . import registry, site_build, validate
from .adapters import gwas_catalog
from .io_tables import load_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-live", action="store_true", help="skip connectivity check and registry ontology check")
    parser.add_argument("--check", action="store_true", help="build only; caller diffs output against git")
    args = parser.parse_args(argv)

    if not args.skip_live:
        print("== connectivity check ==")
        print(gwas_catalog.check_connectivity())

    print("== validate ==")
    validate.run()

    if not args.skip_live:
        print("== registry (live EFO/MONDO term check) ==")
        tables = load_all()
        report = registry.check_registry(tables["phenotypes"])
        print(f"checked {len(report['checked'])} pinned terms; obsolete={report['obsolete']}; unmapped={report['unmapped']}")
        if report["obsolete"]:
            print("::error:: obsolete ontology terms found, blocking release", file=sys.stderr)
            return 1

    print("== site build ==")
    site_build.build(check=args.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
