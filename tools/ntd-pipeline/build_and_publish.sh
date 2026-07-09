#!/usr/bin/env bash
# build_and_publish.sh — render the NTD Intelligence section.
# Usage:
#   ./build_and_publish.sh                 # indicative burden, mock therapeutics (no network)
#   ./build_and_publish.sh gbd_export.csv  # live Open Targets + CT.gov, authoritative burden
#
# It does NOT git-push. Review the generated ./ntd/ output, then commit/push per
# AGENT_INSTRUCTIONS.md step 8.
set -euo pipefail
cd "$(dirname "$0")"

GBD_CSV="${1:-}"

python3 -m pip install -r requirements.txt -q || true

if [[ -n "$GBD_CSV" && -f "$GBD_CSV" ]]; then
  echo ">> Live run with GBD burden: $GBD_CSV"
  python3 pipeline.py --burden-csv "$GBD_CSV" --drugs 8 --targets 8
else
  echo ">> No GBD export supplied — using indicative seed + mock therapeutics."
  echo "   (For a publishable page, pass a GBD export: ./build_and_publish.sh gbd_export.csv)"
  python3 pipeline.py --mock --no-trials
fi

python3 render_html.py

echo
echo ">> Done. Generated section in ./ntd/"
echo "   Preview:  ntd/index.html"
echo "   Next:     copy ./ntd/ into the site root, wire nav, then git add/commit/push"
echo "             (see AGENT_INSTRUCTIONS.md steps 5-8)."
