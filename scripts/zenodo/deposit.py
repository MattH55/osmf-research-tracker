#!/usr/bin/env python3
"""Deposit OSMF dataset bundles to Zenodo (see ZENODO_DEPOSIT_AGENT_TASK.md).

Defaults are the safe ones: sandbox, draft only. Production publishing needs
both --production and --publish, and should only be run after the owner has
approved the specific record.

    python scripts/zenodo/deposit.py --check                      # offline: bundles + metadata only
    python scripts/zenodo/deposit.py --record R1 R2               # sandbox drafts
    python scripts/zenodo/deposit.py --record R1 --publish        # sandbox, published
    python scripts/zenodo/deposit.py --production --record R1     # production DRAFT
    python scripts/zenodo/deposit.py --production --record R1 --publish   # owner-approved only

Tokens come from the environment only: ZENODO_SANDBOX_TOKEN / ZENODO_TOKEN
(scopes deposit:write, deposit:actions). They are never printed or logged.

Flow per record: create deposition with prereserve_doi -> rebuild the bundle
with the reserved DOI stamped into README.md -> stream each file to the bucket
and verify its md5 -> set metadata -> optionally publish. Each run writes a log
to deposit/zenodo/runs/ and records results in deposit/zenodo/state.json so a
rerun resumes the existing draft instead of creating a duplicate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist" / "zenodo"
META = ROOT / "deposit" / "zenodo"
STATE = META / "state.json"
RUNS = META / "runs"
APPROVED = ["R1", "R2", "R3", "R4"]          # first batch approved by the owner on 2026-10-25
LICENCES = {"R1": "cc-by-4.0", "R2": "cc-by-4.0", "R3": "cc-by-4.0", "R4": "cc-by-4.0",
            "R5": "cc-by-sa-4.0", "R6": "cc-by-sa-4.0"}   # R5/R6 licence chosen 2026-10-25; records still blocked


class Zenodo:
    def __init__(self, production: bool):
        import requests  # imported lazily so --check works without it
        self.requests = requests
        self.base = "https://zenodo.org/api" if production else "https://sandbox.zenodo.org/api"
        var = "ZENODO_TOKEN" if production else "ZENODO_SANDBOX_TOKEN"
        token = os.environ.get(var)
        if not token:
            raise SystemExit(f"{var} is not set. Set it in the environment (never on the command line) and rerun.")
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def call(self, method: str, url: str, retry: bool = True, **kw):
        url = url if url.startswith("http") else self.base + url
        for attempt in range(6):
            r = self.s.request(method, url, timeout=600, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and retry:
                time.sleep(min(2 ** attempt * 5, 120))
                continue
            if r.status_code >= 400:
                raise SystemExit(f"{method} {url.replace(self.base, '')} -> {r.status_code}: {r.text[:600]}")
            return r.json() if r.content else {}
        raise SystemExit(f"{method} {url} kept failing after retries")


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(rid: str) -> list[str]:
    """Offline checks; returns problems."""
    problems = []
    bundle, meta_path = DIST / rid, META / f"{rid}.metadata.json"
    if not bundle.is_dir():
        return [f"{rid}: bundle missing; run scripts/zenodo/build_bundles.py --record {rid}"]
    if not meta_path.exists():
        return [f"{rid}: metadata missing at {meta_path.relative_to(ROOT)}"]
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    files = [f for f in bundle.iterdir() if f.is_file()]
    if len(files) > 100:
        problems.append(f"{rid}: {len(files)} files (Zenodo max 100)")
    for key in ("title", "description", "creators", "license", "upload_type", "access_right"):
        if not meta.get(key):
            problems.append(f"{rid}: metadata.{key} missing")
    if meta.get("license") != LICENCES.get(rid):
        problems.append(f"{rid}: licence {meta.get('license')} != approved {LICENCES.get(rid)}")
    if [c.get("orcid") for c in meta.get("creators", [])] != ["0000-0003-2487-0636"]:
        problems.append(f"{rid}: creators must be Matthew Halma only (owner decision 2026-10-25)")
    valid_rel = {"isDocumentedBy", "isDerivedFrom", "isSupplementTo", "isPartOf", "hasPart", "references",
                 "isReferencedBy", "isNewVersionOf", "isPreviousVersionOf", "cites", "isCitedBy"}
    for ri in meta.get("related_identifiers", []):
        if ri.get("relation") not in valid_rel:
            problems.append(f"{rid}: unexpected relation {ri.get('relation')}")
    sums = (bundle / "CHECKSUMS.sha256").read_text(encoding="utf-8").split("\n")
    for line in filter(None, sums):
        digest, name = line.split("  ", 1)
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != digest:
            problems.append(f"{rid}: checksum mismatch for {name}")
    if rid == "R3":
        for f in files:
            if f.suffix == ".json" and '"abstract"' in f.read_text(encoding="utf-8"):
                problems.append(f"{rid}: {f.name} still contains abstracts")
    return problems


def deposit(z: Zenodo, rid: str, env: str, publish: bool, state: dict, log: list) -> None:
    meta = json.loads((META / f"{rid}.metadata.json").read_text(encoding="utf-8"))
    key = f"{env}:{rid}"
    rec = state.get(key, {})
    if rec.get("published"):
        print(f"{rid}: already published on {env} ({rec.get('doi')}); use a new-version flow instead")
        return

    if rec.get("id"):
        dep = z.call("GET", f"/deposit/depositions/{rec['id']}")
        if dep.get("submitted"):
            rec.update(published=True, doi=dep.get("doi"), conceptdoi=dep.get("conceptdoi"))
            state[key] = rec
            save_state(state)
            print(f"{rid}: was already published ({dep.get('doi')})")
            return
    else:
        dep = z.call("POST", "/deposit/depositions", json={"metadata": {"prereserve_doi": True}})
        rec = {"id": dep["id"], "created": datetime.now(timezone.utc).isoformat()}
        state[key] = rec
        save_state(state)
    doi = dep["metadata"]["prereserve_doi"]["doi"]
    rec.update(reserved_doi=doi, url=dep["links"]["html"])
    save_state(state)

    # Rebuild the bundle with the reserved DOI in README + checksums (metadata file is kept as is).
    subprocess.run([sys.executable, str(ROOT / "scripts/zenodo/build_bundles.py"), "--record", rid,
                    "--reserved-doi", f"{rid}={doi}"], check=True, cwd=ROOT)
    problems = check(rid)
    if problems:
        raise SystemExit("\n".join(problems))

    bucket = dep["links"]["bucket"]
    existing = {f["filename"]: f for f in z.call("GET", f"/deposit/depositions/{rec['id']}/files")}
    for f in sorted((DIST / rid).iterdir()):
        local = md5(f)
        remote = existing.get(f.name)
        if remote and remote.get("checksum") == local:
            continue
        if remote:
            z.call("DELETE", f"/deposit/depositions/{rec['id']}/files/{remote['id']}")
        with f.open("rb") as fh:
            up = z.call("PUT", f"{bucket}/{f.name}", data=fh, headers={"Content-Type": "application/octet-stream"})
        got = (up.get("checksum") or "").replace("md5:", "")
        if got != local:
            raise SystemExit(f"{rid}: md5 mismatch after upload of {f.name}: {got} != {local}")
        log.append({"record": rid, "file": f.name, "bytes": f.stat().st_size, "md5": local})

    body = dict(meta)
    body["prereserve_doi"] = True
    z.call("PUT", f"/deposit/depositions/{rec['id']}", json={"metadata": body})
    print(f"{rid}: draft ready on {env}: {rec['url']}  reserved DOI {doi}")

    if publish:
        try:
            pub = z.call("POST", f"/deposit/depositions/{rec['id']}/actions/publish", retry=False)
        except SystemExit:
            pub = z.call("GET", f"/deposit/depositions/{rec['id']}")   # never blindly retry a publish
            if not pub.get("submitted"):
                raise
        rec.update(published=True, doi=pub.get("doi"), conceptdoi=pub.get("conceptdoi"),
                   record_url=pub["links"].get("record_html") or pub["links"].get("html"))
        print(f"{rid}: PUBLISHED on {env}: DOI {rec['doi']}  concept DOI {rec['conceptdoi']}")
    state[key] = rec
    save_state(state)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", nargs="*", default=APPROVED)
    ap.add_argument("--production", action="store_true", help="use zenodo.org (default: sandbox)")
    ap.add_argument("--publish", action="store_true", help="publish after upload (default: leave a draft)")
    ap.add_argument("--check", action="store_true", help="offline checks only")
    args = ap.parse_args()

    blocked = [r for r in args.record if r not in APPROVED]
    if blocked:
        raise SystemExit(f"not approved for deposit: {', '.join(blocked)} (see ZENODO_GATE1_REPORT.md)")
    problems = [p for rid in args.record for p in check(rid)]
    for p in problems:
        print("PROBLEM", p)
    if args.check:
        print("checks passed" if not problems else f"{len(problems)} problem(s)")
        sys.exit(1 if problems else 0)
    if problems:
        sys.exit(1)
    if args.production and args.publish:
        print("Publishing on zenodo.org is permanent. Records:", ", ".join(args.record))

    env = "production" if args.production else "sandbox"
    z = Zenodo(args.production)
    META.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    state, log = load_state(), []
    try:
        for rid in args.record:
            deposit(z, rid, env, args.publish, state, log)
    finally:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (RUNS / f"{stamp}-{env}.json").write_text(json.dumps({"env": env, "records": args.record,
                                                              "publish": args.publish, "uploads": log,
                                                              "state": {k: v for k, v in state.items()
                                                                        if k.startswith(env)}}, indent=2) + "\n",
                                                  encoding="utf-8")


if __name__ == "__main__":
    main()
