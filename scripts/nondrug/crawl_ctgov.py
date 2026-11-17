#!/usr/bin/env python3
"""Crawl ClinicalTrials.gov for non-drug-type interventional trials, one query per condition.

Conditions: every condition in data/disease-intelligence/*.json (queried by its name, as the
condition pipeline does) plus the post-viral conditions the tracker follows.

Query per condition:
    query.cond=<name>
    filter.advanced=AREA[StudyType]INTERVENTIONAL AND
                    AREA[InterventionType](BEHAVIORAL OR DEVICE OR DIETARY_SUPPLEMENT OR OTHER OR PROCEDURE)
    sort=LastUpdatePostDate:desc, pageSize=CAP (default 1000)

The cap is recorded per condition (``total`` vs ``fetched``) and printed on every page that uses it.
Raw responses are cached in data/nondrug/cache/ (git-ignored); re-runs reuse the cache unless
--refresh is given. This crawl is NOT part of the daily job: run it monthly or when conditions change.

    python scripts/nondrug/crawl_ctgov.py            # all conditions, use cache
    python scripts/nondrug/crawl_ctgov.py --refresh  # re-fetch everything
    python scripts/nondrug/crawl_ctgov.py --only fibromyalgia long-covid
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conditions import load_conditions  # noqa: E402

API = "https://clinicaltrials.gov/api/v2/studies"
CACHE = ROOT / "data" / "nondrug" / "cache"
FIELDS = ",".join([
    "NCTId", "BriefTitle", "OverallStatus", "StartDate", "PrimaryCompletionDate", "CompletionDate",
    "LastUpdatePostDate", "Phase", "EnrollmentCount", "DesignAllocation", "ArmGroupLabel", "ArmGroupType",
    "InterventionType", "InterventionName", "InterventionArmGroupLabel", "PrimaryOutcomeMeasure",
    "PrimaryOutcomeDescription", "Condition", "HasResults",
])
FILTER = ("AREA[StudyType]INTERVENTIONAL AND "
          "AREA[InterventionType](BEHAVIORAL OR DEVICE OR DIETARY_SUPPLEMENT OR OTHER OR PROCEDURE)")
# Second pass: named supplements that registries often record as DRUG (so the first filter misses them).
SUPPLEMENT_TERMS = ("vitamin D OR cholecalciferol OR omega-3 OR fish oil OR probiotic OR coenzyme Q10 OR ubiquinol OR "
                    "melatonin OR magnesium OR zinc OR creatine OR nicotinamide riboside OR N-acetylcysteine OR "
                    "vitamin C OR vitamin B12 OR folic acid OR curcumin OR quercetin OR resveratrol")
SUPP_FILTER = "AREA[StudyType]INTERVENTIONAL AND AREA[InterventionType](DRUG OR BIOLOGICAL)"
HEADERS = {"User-Agent": "OSMF-research-tracker/1.0 (+https://research.opensourcemed.info; non-drug evidence map)",
           "Accept": "application/json"}
_last = 0.0


def get(params: dict) -> dict:
    """GET with the registry's 1 request/second limit and simple retries."""
    global _last
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        wait = 1.1 - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # network or 429/5xx
            backoff = 5 * (attempt + 1)
            print(f"    retry {attempt + 1} after {type(e).__name__}: {str(e)[:80]} (sleep {backoff}s)")
            time.sleep(backoff)
    raise RuntimeError(f"ClinicalTrials.gov request failed after retries: {url[:160]}")


def crawl(cond: dict, cap: int, refresh: bool, supplements: bool = False) -> dict:
    out = CACHE / (f"{cond['slug']}.supp.json" if supplements else f"{cond['slug']}.json")
    if out.exists() and not refresh:
        return json.loads(out.read_text(encoding="utf-8"))
    params = {"query.cond": cond["query"], "filter.advanced": SUPP_FILTER if supplements else FILTER, "countTotal": "true",
              "sort": "LastUpdatePostDate:desc", "fields": FIELDS, "format": "json"}
    if supplements:
        params["query.intr"] = SUPPLEMENT_TERMS
    studies, token, total = [], None, None
    while len(studies) < cap:
        params["pageSize"] = str(min(1000, cap - len(studies)))
        if token:
            params["pageToken"] = token
        d = get(params)
        total = d.get("totalCount", total)
        studies += d.get("studies", [])
        token = d.get("nextPageToken")
        if not token or not d.get("studies"):
            break
    payload = {"slug": cond["slug"], "name": cond["name"], "query": cond["query"], "total": total,
               "fetched": len(studies), "cap": cap, "fetched_at": time.strftime("%Y-%m-%d"), "studies": studies}
    CACHE.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=1000)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--supplements", action="store_true", help="second pass: named supplements registered as drugs")
    a = ap.parse_args()
    conds = [c for c in load_conditions() if not a.only or c["slug"] in a.only]
    print(f"crawling {len(conds)} conditions, cap {a.cap} trials each")
    capped = []
    for i, c in enumerate(conds, 1):
        p = crawl(c, a.cap, a.refresh, a.supplements)
        flag = " (CAPPED)" if (p["total"] or 0) > p["fetched"] else ""
        if flag:
            capped.append(c["slug"])
        print(f"  [{i}/{len(conds)}] {c['slug']}: {p['fetched']} of {p['total']}{flag}")
    print(f"done; {len(capped)} conditions hit the cap: {', '.join(capped)}")


if __name__ == "__main__":
    main()
