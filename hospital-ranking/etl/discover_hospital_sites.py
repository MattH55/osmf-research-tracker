#!/usr/bin/env python3
"""
Discover candidate websites for CMS hospitals, so ingest_mrf_prices.py knows where
to look for each hospital's cms-hpt.txt (45 CFR 180.50(d)(6)).

Sources:
  * wikidata  - U.S. hospitals (P31/P279* Q16917, P17 Q30) with an official website
                (P856), coordinates (P625) and the located-in place (P131). CC0.
  * osm       - OpenStreetMap amenity=hospital with website / contact:website, via
                Overpass (tries several public servers; skipped if all fail). ODbL.
  * manual    - data/cms/hospital-sites.manual.json; entries there always win
                (they replace the discovered candidates for that CCN).

A candidate is attached to a CMS hospital (data/cms/hospitals.json, read-only)
only when the normalised name matches strongly (identical distinctive name tokens,
or one name's tokens containing the other's with >= 2 shared, one non-generic, and
no unmatched facility-kind word) AND the location agrees (same city + state, or
within 2 miles of the hospital's coordinates). A candidate is only a place to look:
the ingest attaches prices only through a strict cms-hpt location-name match.

Raw source responses are cached in data/mrf/cache/discovery/ (gitignored);
--offline rebuilds from that cache. A source that fails keeps its previous
candidates from hospital-sites.json, so one flaky server never drops coverage.

Output: data/cms/hospital-sites.json
  { "<CCN>": { "candidates": [ {"url", "source", "match"} ], "updated": "YYYY-MM-DD" } }
"updated" changes only when that hospital's candidate list changes.

USAGE:
  python etl/discover_hospital_sites.py [--sources wikidata,osm] [--offline]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from price_contract import (  # noqa: E402
    CMS_DIR,
    ROOT,
    GENERIC_ONLY,
    atomic_write_text,
    distinctive,
    dump_json,
    kind_compatible,
    load_hospitals,
    name_tokens,
    norm_city,
    read_json,
)

SITES_JSON = CMS_DIR / "hospital-sites.json"
MANUAL_JSON = CMS_DIR / "hospital-sites.manual.json"
CACHE_DIR = ROOT / "data" / "mrf" / "cache" / "discovery"
USER_AGENT = ("OpenSourceMed-HospitalCompare/1.0 (+https://opensourcemed.info; contact@opensourcemed.info) "
              "hospital-site-discovery")
MAX_MILES = 2.0
SOURCE_ORDER = {"manual": 0, "wikidata": 1, "osm": 2}

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_QUERY_FULL = """
SELECT ?item ?itemLabel ?website ?coord ?placeLabel ?iso WHERE {
  ?item wdt:P31/wdt:P279* wd:Q16917 ;
        wdt:P17 wd:Q30 ;
        wdt:P856 ?website .
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item wdt:P131 ?place . }
  OPTIONAL { ?item wdt:P131/wdt:P131* ?st . ?st wdt:P300 ?iso . FILTER(STRSTARTS(?iso, "US-")) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""
# Fallback without the state lookup (cheaper if the full query times out).
WIKIDATA_QUERY_SIMPLE = """
SELECT ?item ?itemLabel ?website ?coord ?placeLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q16917 ;
        wdt:P17 wd:Q30 ;
        wdt:P856 ?website .
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item wdt:P131 ?place . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OVERPASS_QUERY = """
[out:json][timeout:900];
area["ISO3166-1"="US"][admin_level=2]->.us;
(
  nwr["amenity"="hospital"]["website"](area.us);
  nwr["amenity"="hospital"]["contact:website"](area.us);
);
out center tags;
"""

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "puerto rico": "PR", "guam": "GU", "virgin islands": "VI",
}


# ============================================================ helpers

def log(msg: str) -> None:
    print(msg, flush=True)


def miles(lat1, lon1, lat2, lon2) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def clean_url(u: str | None) -> str | None:
    if not u:
        return None
    u = str(u).strip().split(";")[0].strip()
    if not re.match(r"^https?://", u, re.I):
        if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/|$)", u, re.I):
            u = "https://" + u
        else:
            return None
    host = urlparse(u).hostname
    if not host or "." not in host:
        return None
    return u


def host_key(u: str) -> str:
    h = (urlparse(u).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def state_code(val: str | None) -> str | None:
    if not val:
        return None
    v = val.strip()
    if re.fullmatch(r"[A-Za-z]{2}", v):
        return v.upper()
    if v.upper().startswith("US-") and len(v) == 5:
        return v[3:].upper()
    return US_STATES.get(v.lower())


def name_match(src_toks: frozenset, cms_toks: frozenset) -> str | None:
    if not src_toks or not cms_toks or not distinctive(src_toks):
        return None
    if src_toks == cms_toks:
        return "name"
    shared = src_toks & cms_toks
    if (len(shared) >= 2 and distinctive(shared) and (src_toks <= cms_toks or cms_toks <= src_toks)
            and kind_compatible(src_toks, cms_toks) and kind_compatible(cms_toks, src_toks)):
        return "name-subset"
    return None


# ============================================================ sources

def http_post(url: str, data: dict, timeout: int, headers: dict | None = None) -> requests.Response:
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    return requests.post(url, data=data, headers=h, timeout=timeout)


def fetch_wikidata() -> dict:
    for label, query in (("full", WIKIDATA_QUERY_FULL), ("simple", WIKIDATA_QUERY_SIMPLE)):
        for attempt in range(3):
            try:
                log(f"Wikidata: querying ({label})…")
                r = http_post(WIKIDATA_ENDPOINT, {"query": query, "format": "json"}, timeout=330,
                              headers={"Accept": "application/sparql-results+json"})
                if r.status_code == 429 or r.status_code >= 500:
                    wait = min(120, int(r.headers.get("Retry-After") or 0) or 10 * (attempt + 1))
                    log(f"  HTTP {r.status_code}; retrying in {wait}s")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as exc:
                log(f"  Wikidata {label} query failed: {str(exc)[:160]}")
                break
    raise RuntimeError("all Wikidata queries failed")


def wikidata_records(raw: dict) -> list[dict]:
    items: dict[str, dict] = {}
    for b in raw.get("results", {}).get("bindings", []):
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        rec = items.setdefault(qid, {"source": f"wikidata:{qid}", "names": set(), "urls": set(),
                                     "coords": set(), "cities": set(), "states": set()})
        if "itemLabel" in b:
            rec["names"].add(b["itemLabel"]["value"])
        u = clean_url(b.get("website", {}).get("value"))
        if u:
            rec["urls"].add(u)
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", b.get("coord", {}).get("value", ""))
        if m:
            rec["coords"].add((float(m.group(2)), float(m.group(1))))
        if "placeLabel" in b:
            rec["cities"].add(b["placeLabel"]["value"])
        st = state_code(b.get("iso", {}).get("value"))
        if st:
            rec["states"].add(st)
    return [items[k] for k in sorted(items)]


def fetch_osm() -> dict:
    last = None
    for server in OVERPASS_SERVERS:
        for attempt in range(2):
            try:
                log(f"OSM: querying {server}…")
                r = http_post(server, {"data": OVERPASS_QUERY}, timeout=960)
                if r.status_code == 429 or r.status_code >= 500:
                    last = f"HTTP {r.status_code}"
                    log(f"  {last}")
                    time.sleep(min(60, int(r.headers.get("Retry-After") or 0) or 15 * (attempt + 1)))
                    continue
                r.raise_for_status()
                doc = r.json()
                if "elements" not in doc:
                    raise ValueError("no elements in Overpass response")
                if doc.get("remark") and "error" in doc["remark"].lower():
                    raise ValueError(doc["remark"][:200])
                return doc
            except (requests.RequestException, ValueError) as exc:
                last = str(exc)[:200]
                log(f"  failed: {last}")
                break
    raise RuntimeError(f"all Overpass servers failed (last: {last})")


def osm_records(raw: dict) -> list[dict]:
    out = []
    for el in sorted(raw.get("elements", []), key=lambda e: (e.get("type", ""), e.get("id", 0))):
        tags = el.get("tags") or {}
        urls = {u for u in (clean_url(tags.get("website")), clean_url(tags.get("contact:website"))) if u}
        names = {tags[k] for k in ("name", "official_name", "alt_name", "operator:name") if tags.get(k)}
        if not urls or not names:
            continue
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        st = state_code(tags.get("addr:state"))
        out.append({
            "source": f"osm:{el['type']}/{el['id']}",
            "names": names, "urls": urls,
            "coords": {(float(lat), float(lon))} if lat is not None and lon is not None else set(),
            "cities": {tags["addr:city"]} if tags.get("addr:city") else set(),
            "states": {st} if st else set(),
        })
    return out


# ============================================================ matching

class Matcher:
    def __init__(self, hospitals: list[dict]):
        self.hospitals = hospitals
        self.by_token: dict[str, list[tuple[dict, frozenset]]] = defaultdict(list)
        for h in hospitals:
            toks = name_tokens(h.get("name", ""))
            for t in toks - GENERIC_ONLY:
                self.by_token[t].append((h, toks))

    def match(self, rec: dict) -> list[tuple[str, str]]:
        """[(ccn, how)] for every CMS hospital this record matches strongly."""
        found: dict[str, str] = {}
        for name in sorted(rec["names"]):
            st = name_tokens(name)
            if not distinctive(st):
                continue
            seen = set()
            for t in sorted(st - GENERIC_ONLY):
                for h, ht in self.by_token.get(t, []):
                    ccn = h["cmsProviderId"]
                    if ccn in seen or ccn in found:
                        continue
                    seen.add(ccn)
                    how = name_match(st, ht)
                    if not how:
                        continue
                    loc = self.location(rec, h)
                    if loc:
                        found[ccn] = f"{how}+{loc}"
        return sorted(found.items())

    @staticmethod
    def location(rec: dict, h: dict) -> str | None:
        lat, lon = h.get("latitude"), h.get("longitude")
        if lat is not None and lon is not None:
            for (a, b) in sorted(rec["coords"]):
                d = miles(lat, lon, a, b)
                if d <= MAX_MILES:
                    return f"{d:.1f}mi"
        hc = norm_city(h.get("city"))
        hs = (h.get("state") or "").upper()
        if hc and hs and hs in rec["states"] and hc in {norm_city(c) for c in rec["cities"]}:
            return "city+state"
        return None


# ============================================================ manual

MANUAL_TEMPLATE = {
    "_comment": (
        "Manual website overrides for etl/discover_hospital_sites.py. Keys are CMS CCNs "
        "(data/cms/hospitals.json cmsProviderId). Value: a list of website URLs (strings) or "
        "objects {\"url\": \"https://...\", \"note\": \"why\"}. An entry here REPLACES the "
        "discovered candidates for that CCN; an empty list suppresses them. The ingest still "
        "requires a strict cms-hpt.txt location-name match before attaching any price."
    ),
}


def load_manual() -> dict[str, list[dict]]:
    doc = read_json(MANUAL_JSON, None)
    if doc is None:
        atomic_write_text(MANUAL_JSON, dump_json(MANUAL_TEMPLATE))
        doc = MANUAL_TEMPLATE
    out: dict[str, list[dict]] = {}
    for ccn, vals in doc.items():
        if ccn.startswith("_"):
            continue
        cands = []
        for v in vals or []:
            u = clean_url(v if isinstance(v, str) else (v or {}).get("url"))
            if u:
                note = None if isinstance(v, str) else (v or {}).get("note")
                cands.append({"url": u, "source": "manual", "match": note or "manual override"})
        out[ccn] = cands
    return out


# ============================================================ main

def load_source(name: str, offline: bool) -> tuple[list[dict] | None, str]:
    cache = CACHE_DIR / f"{name}.json"
    fetch, parse = (fetch_wikidata, wikidata_records) if name == "wikidata" else (fetch_osm, osm_records)
    if not offline:
        try:
            raw = fetch()
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            atomic_write_text(cache, json.dumps(raw, ensure_ascii=False))
            return parse(raw), "fetched"
        except Exception as exc:  # noqa: BLE001 - never fail the whole run on one source
            log(f"{name}: unavailable ({str(exc)[:200]}); falling back to cache")
    raw = read_json(cache, None)
    if raw is None:
        return None, "unavailable"
    return parse(raw), "cache"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sources", default="wikidata,osm", help="comma list of: wikidata, osm")
    ap.add_argument("--offline", action="store_true", help="use cached source responses only")
    args = ap.parse_args()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    bad = set(sources) - {"wikidata", "osm"}
    if bad:
        ap.error(f"unknown source(s): {sorted(bad)}")

    hospitals = load_hospitals()
    ccns = {h["cmsProviderId"] for h in hospitals}
    matcher = Matcher(hospitals)
    previous = read_json(SITES_JSON, {}) or {}
    today = date.today().isoformat()

    found: dict[str, list[dict]] = defaultdict(list)
    status: dict[str, str] = {}
    for name in sources:
        recs, how = load_source(name, args.offline)
        status[name] = how
        if recs is None:
            # Keep this source's previous candidates rather than dropping them.
            kept = 0
            for ccn, entry in previous.items():
                for c in entry.get("candidates", []):
                    if c.get("source", "").startswith(name + ":") and ccn in ccns:
                        found[ccn].append(c)
                        kept += 1
            log(f"{name}: no data this run; kept {kept} previous candidate(s)")
            continue
        n = 0
        for rec in recs:
            for ccn, how_m in matcher.match(rec):
                for u in sorted(rec["urls"]):
                    found[ccn].append({"url": u, "source": rec["source"], "match": how_m})
                    n += 1
        log(f"{name} [{how}]: {len(recs)} record(s) with a website -> {n} candidate link(s)")

    manual = load_manual()
    for ccn, cands in manual.items():
        if ccn not in ccns:
            log(f"manual: CCN {ccn} not in hospitals.json; ignored")
            continue
        found[ccn] = list(cands)

    out: dict[str, dict] = {}
    for ccn in sorted(found):
        cands = sorted(found[ccn], key=lambda c: (SOURCE_ORDER.get(c["source"].split(":")[0], 9),
                                                  c["source"], c["url"]))
        seen_hosts: set[str] = set()
        uniq = []
        for c in cands:
            k = host_key(c["url"])
            if k in seen_hosts:
                continue
            seen_hosts.add(k)
            uniq.append({"url": c["url"], "source": c["source"], "match": c["match"]})
        if not uniq:
            continue
        prev = previous.get(ccn) or {}
        updated = prev.get("updated") if prev.get("candidates") == uniq and prev.get("updated") else today
        out[ccn] = {"candidates": uniq, "updated": updated}

    atomic_write_text(SITES_JSON, json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n")

    by_source: Counter = Counter()
    for entry in out.values():
        for s in {c["source"].split(":")[0] for c in entry["candidates"]}:
            by_source[s] += 1
    log(f"\nWrote {SITES_JSON}")
    log(f"Source status: {json.dumps(status)}")
    log(f"CMS hospitals with >= 1 candidate: {len(out)} of {len(hospitals)} "
        f"({100 * len(out) / max(1, len(hospitals)):.1f}%)")
    for s in sorted(by_source, key=lambda s: SOURCE_ORDER.get(s, 9)):
        log(f"  {s:9s} {by_source[s]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
