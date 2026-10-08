#!/usr/bin/env python3
"""Remove trials from EXCLUDED_SPONSORS out of every data file and report.

clinical_trials_agent.py drops such trials at fetch time, but data written
before the exclusion (and the weekly report archive) still carry them.  Run
this, then the normal build chain, to clear every rendered copy.

    python scripts/purge_excluded_trials.py
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "clinical_trials"))
from clinical_trials_agent import EXCLUDED_SPONSORS  # noqa: E402

CARD_OPEN = '<div class="bg-white border border-slate-200 rounded-3xl p-5 mb-4">'


def excluded_ids() -> set[str]:
    ids = set()
    for f in ("clinical_trials/data/clinical_trials_current.json", "clinical_trials/data/trials_state.json"):
        p = ROOT / f
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        recs = d.get("trials", d) if isinstance(d, dict) else d
        recs = recs.values() if isinstance(recs, dict) else recs
        for r in recs:
            if isinstance(r, dict) and (r.get("sponsor") or "").strip().lower() in EXCLUDED_SPONSORS:
                ids.add(r["nct_id"])
    return ids


def walk(o, ids):
    def hit(x):
        return any(i in json.dumps(x) for i in ids)
    if isinstance(o, list):
        return [walk(x, ids) for x in o if not (isinstance(x, (dict, str)) and hit(x))]
    if isinstance(o, dict):
        return {k: walk(v, ids) for k, v in o.items()
                if not (k in ids or (isinstance(v, dict) and v.get("nct_id") in ids))}
    return o


def purge_json(path: Path, ids) -> int:
    s = path.read_text(encoding="utf-8")
    before = sum(s.count(i) for i in ids)
    if not before:
        return 0
    d = walk(json.loads(s), ids)
    if isinstance(d, dict) and "count" in d and isinstance(d.get("trials"), list):
        d["count"] = len(d["trials"])
    out = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
    path.write_text(out, encoding="utf-8")
    return before - sum(out.count(i) for i in ids)


def purge_md(path: Path, ids) -> int:
    s = path.read_text(encoding="utf-8")
    if not any(i in s for i in ids):
        return 0
    blocks = s.split("\n---\n")
    keep = [b for b in blocks if not any(i in b for i in ids)]
    path.write_text("\n---\n".join(keep), encoding="utf-8")
    return len(blocks) - len(keep)


def purge_report_html(path: Path, ids) -> int:
    s = path.read_text(encoding="utf-8")
    if not any(i in s for i in ids):
        return 0
    parts = s.split(CARD_OPEN)
    out = [parts[0]]
    removed = 0
    for p in parts[1:]:
        if any(i in p for i in ids):
            k = p.find("View on ClinicalTrials.gov")
            end = k
            for _ in range(3):
                end = p.find("</div>", end) + len("</div>")
            if k < 0:
                out.append(CARD_OPEN + p)
                continue
            out[-1] = out[-1].rstrip() + "\n" + p[end:].lstrip("\n")
            removed += 1
        else:
            out.append(CARD_OPEN + p)
    path.write_text("".join(out), encoding="utf-8")
    return removed


def purge_inline_json(path: Path, ids) -> int:
    """clinical_trials-local.html embeds the trial list as JSON objects."""
    s = path.read_text(encoding="utf-8")
    removed = 0
    for nct in ids:
        key = f'{{"nct_id": "{nct}"'
        while key in s:
            i = s.find(key)
            d = 0
            j = i
            instr = esc = False
            while True:
                c = s[j]
                if instr:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        instr = False
                elif c == '"':
                    instr = True
                elif c == "{":
                    d += 1
                elif c == "}":
                    d -= 1
                    if d == 0:
                        j += 1
                        break
                j += 1
            if s[j:j + 2] == ", ":
                j += 2
            elif s[j:j + 1] == ",":
                j += 1
            elif s[i - 2:i] == ", ":
                i -= 2
            s = s[:i] + s[j:]
            removed += 1
    if removed:
        path.write_text(s, encoding="utf-8")
    return removed


def main() -> None:
    ids = excluded_ids()
    # ids seen in earlier runs stay purged from the archive even once the
    # current data no longer carries them
    ids |= {"NCT06967428"}
    print("excluded trial ids:", sorted(ids))
    for pat in ("clinical_trials/data/*.json", "data/therapeutic_agents.json",
                "data/clinical_trials/*.json", "data/biomarkers/*.json"):
        for f in glob.glob(str(ROOT / pat)):
            n = purge_json(Path(f), ids)
            if n:
                print(f"  {Path(f).relative_to(ROOT)}: -{n} mentions")
    for f in glob.glob(str(ROOT / "clinical_trials/reports/*.md")):
        n = purge_md(Path(f), ids)
        if n:
            print(f"  {Path(f).relative_to(ROOT)}: -{n} blocks")
    for f in glob.glob(str(ROOT / "clinical_trials/reports/*.html")):
        n = purge_report_html(Path(f), ids)
        if n:
            print(f"  {Path(f).relative_to(ROOT)}: -{n} cards")
    local = ROOT / "clinical_trials-local.html"
    if local.exists():
        n = purge_inline_json(local, ids)
        if n:
            print(f"  {local.name}: -{n} records")


if __name__ == "__main__":
    main()
