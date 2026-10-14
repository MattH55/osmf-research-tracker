#!/usr/bin/env python3
"""
Shared price-row contract for the HospitalCompare MRF pipeline.

Every ingest (ingest_trilliant.py, ingest_mrf_prices.py), the observation-store
migration and the browser-data build use this module, so the rules live in one
place:

  * Only prices a hospital actually published in its machine-readable file
    (MRF). No modelled, estimated or derived figures. Cash fields hold only the
    published discounted cash price; gross charge is never copied into them.
  * Code matching requires an explicit code type (MS-DRG:<n>, CPT:<n>,
    HCPCS:<n>). Each code belongs to exactly one procedure; each procedure has
    exactly one canonical scope (see data/seed/procedures.json "scope").
  * Bounds: any value <= 0, >= $500,000 or a sentinel is dropped; each procedure
    has a plausibility floor (procedures.json "priceFloorUsd").
  * Provenance: priceVintage comes from the source file, never the build date.
  * Hospital attachment is strict (exact CCN when the source has one, else exact
    name + city/state); procedures incompatible with the hospital type are
    blocked.

Anything that fails a rule is quarantined with a reason (data/cms/quarantine.json).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import time
import uuid
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMS_DIR = ROOT / "data" / "cms"
HOSPITALS_JSON = CMS_DIR / "hospitals.json"
PROCEDURES_JSON = ROOT / "data" / "seed" / "procedures.json"
QUARANTINE_JSON = CMS_DIR / "quarantine.json"

PRICE_CEILING = 500_000
SENTINELS = {999999999.0, 99999999.0, 9999999.0, 999999.0, 99999.99, 999999.99, 9999999.99}
STALE_MONTHS = 18
# App-level floors (src/lib/pricing.ts); per-procedure floors in procedures.json are >= these.
SCOPE_FLOOR = {"inpatient_stay": 1500, "facility_service": 15, "professional": 15}

VALID_SCOPES = ("inpatient_stay", "facility_service", "professional")
VALID_SOURCES = ("trilliant_mrf", "hospital_mrf")

# Negotiated-rate methodologies we accept when the source gives a dollar amount.
# per diem (a daily rate, not the service/stay price) and percent-of-charges are
# excluded; we never convert percentages or algorithms to dollars ourselves.
EXCLUDED_METHODOLOGIES = {"per diem", "percent of total billed charges", "percentage of total billed charges"}

# Hospital types (data/cms/hospitals.json hospitalType) that cannot be the
# site of these services. Psychiatric and long-term care hospitals don't do
# elective surgery, endoscopy or deliveries; only imaging is allowed there.
# Rural Emergency Hospitals have no inpatient beds by statute (42 CFR 485.502).
NON_SURGICAL_TYPES = {"Psychiatric", "Long-term"}
NO_INPATIENT_TYPES = {"Rural Emergency Hospital"}
IMAGING_CATEGORY = "Imaging"

ROW_KEY_ORDER = [
    "id",
    "hospitalId",
    "cmsProviderId",
    "procedureId",
    "priceSource",
    "scope",
    "matchType",
    "matchedCodes",
    "cashLow",
    "cashMedian",
    "cashHigh",
    "negotiatedLow",
    "negotiatedMedian",
    "negotiatedHigh",
    "payerCount",
    "grossCharge",
    "priceVintage",
    "stale",
    "mrfUrl",
    "sourceDataset",
    "sourceDocumentHash",
    "sourceRetrievedAt",
    "sourceFacilityName",
    "hospitalMatch",
    "lineCount",
]

FORBIDDEN_FIELDS = {"oopUninsured", "oopPpo", "oopHdhp", "estimatedOop", "isEstimate"}


# ---------------------------------------------------------------- IO helpers

def atomic_write_text(path: Path, content: str, retries: int = 8) -> None:
    """Write via temp file + replace to avoid Windows/OneDrive lock errors."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    for attempt in range(retries):
        try:
            tmp.write_text(content, encoding="utf-8", newline="\n")
            tmp.replace(path)
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
        finally:
            if tmp.exists() and not path.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    for attempt in range(8):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            if attempt == 7:
                raise
            time.sleep(1.5 * (attempt + 1))
    return default


def dump_json(obj, indent: int | None = 2) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- procedures

def load_procedures() -> list[dict]:
    return json.loads(PROCEDURES_JSON.read_text(encoding="utf-8"))


class CodeIndex:
    """Explicit-type code -> procedure index built from procedures.json."""

    def __init__(self, procedures: list[dict] | None = None):
        self.procedures = procedures if procedures is not None else load_procedures()
        self.by_id = {p["id"]: p for p in self.procedures}
        self.drg: dict[str, str] = {}
        self.cpt: dict[str, str] = {}
        for p in self.procedures:
            for d in p.get("drgCodes") or []:
                key = normalize_drg(d)
                if key in self.drg:
                    raise ValueError(f"MS-DRG {d} assigned to both {self.drg[key]} and {p['id']}")
                self.drg[key] = p["id"]
            for c in p.get("cptCodes") or []:
                if c in self.cpt:
                    raise ValueError(f"CPT/HCPCS {c} assigned to both {self.cpt[c]} and {p['id']}")
                self.cpt[c] = p["id"]
            scope = p.get("scope")
            if scope not in VALID_SCOPES:
                raise ValueError(f"{p['id']} has no valid canonical scope")
            if scope == "inpatient_stay" and (p.get("cptCodes") or not p.get("drgCodes")):
                raise ValueError(f"{p['id']}: inpatient_stay procedures are priced by MS-DRG only")
            if scope == "facility_service" and (p.get("drgCodes") or not p.get("cptCodes")):
                raise ValueError(f"{p['id']}: facility_service procedures are priced by CPT/HCPCS only")

    def scope(self, proc_id: str) -> str:
        return self.by_id[proc_id]["scope"]

    def floor(self, proc_id: str) -> float:
        p = self.by_id[proc_id]
        return max(float(p.get("priceFloorUsd") or 0), SCOPE_FLOOR[p["scope"]])

    def category(self, proc_id: str) -> str:
        return self.by_id[proc_id].get("category") or ""

    def match_all_codes(self, all_codes: str | None) -> tuple[list[tuple[str, str, str]], list[str]]:
        """Parse a Trilliant/CMS 'all_codes' string ("CDM:1 | RC:450 | CPT:45378").

        Returns (matches, problems). Each match is (procedure_id, match_type,
        matched_code_label). Only tokens whose type is explicitly MS-DRG, CPT or
        HCPCS count. A token with trailing characters (modifier etc.) is a
        problem, not a match.
        """
        matches: list[tuple[str, str, str]] = []
        problems: list[str] = []
        if not all_codes:
            return matches, problems
        for tok in str(all_codes).split("|"):
            tok = tok.strip()
            if ":" not in tok:
                continue
            ctype, _, val = tok.partition(":")
            ctype = ctype.strip().upper()
            val = val.strip().upper()
            if ctype == "MS-DRG":
                if not val.isdigit():
                    continue
                key = normalize_drg(val)
                if key in self.drg:
                    matches.append((self.drg[key], "ms-drg", f"MS-DRG:{key}"))
            elif ctype in ("CPT", "HCPCS"):
                base = val[:5]
                if base in self.cpt:
                    if val != base:
                        problems.append(f"code_with_suffix:{ctype}:{val}")
                        continue
                    matches.append((self.cpt[base], ctype.lower(), f"{ctype}:{base}"))
        return matches, problems


def normalize_drg(code: str) -> str:
    code = str(code).strip()
    return f"{int(code):03d}" if code.isdigit() else code


# ---------------------------------------------------------------- normalizers

def norm_label(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip().strip('"').strip("'").strip().lower()
    if not s or s in ("none", "null", "n/a", "na"):
        return None
    if s == "facilty":
        s = "facility"
    return s


def valid_amount(v, floor: float = 0.0) -> float | None:
    """Return v as float if it is a plausible published dollar amount, else None."""
    if v is None:
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    if n in SENTINELS or n <= 0 or n >= PRICE_CEILING:
        return None
    if n < floor:
        return None
    return n


def amount_problem(v, floor: float) -> str | None:
    """Why a raw value was rejected (None if acceptable or absent)."""
    if v is None:
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "non_numeric"
    if n != n:
        return None
    if n in SENTINELS:
        return "sentinel_value"
    if n <= 0:
        return "value_le_zero"
    if n >= PRICE_CEILING:
        return "value_ge_500k"
    if n < floor:
        return "value_below_procedure_floor"
    return None


def median_round(vals: list[float]) -> int | None:
    return round(statistics.median(vals)) if vals else None


# ---------------------------------------------------------------- dates

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def parse_iso_date(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val.isoformat()[:10]
    s = str(val).strip()
    m = DATE_RE.match(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
        except ValueError:
            return None
    return None


def months_before(ref: str, months: int) -> str:
    d = date.fromisoformat(ref)
    y, m = d.year, d.month - months
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, 28)
    return date(y, m, day).isoformat()


def is_stale(vintage: str, reference_date: str) -> bool:
    return vintage < months_before(reference_date, STALE_MONTHS)


# ---------------------------------------------------------------- ids

def deterministic_id(*parts: str) -> str:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return h[:24]


OBS_NAMESPACE = uuid.UUID("6f1d2c1e-6a43-5b8e-9a51-2f0f6d0c9b11")


def deterministic_uuid(*parts: str) -> str:
    return str(uuid.uuid5(OBS_NAMESPACE, "|".join(str(p) for p in parts)))


# ---------------------------------------------------------------- hospitals

NAME_STOPWORDS = {
    "hospital", "hospitals", "medical", "center", "centre", "ctr", "med", "hosp",
    "health", "healthcare", "the", "of", "and", "inc", "llc", "dba", "d", "b", "a",
    "at", "campus", "system", "systems", "corp", "corporation", "co", "lp", "ltd",
    "pc", "pllc", "facility", "services", "service", "care", "clinic",
}
GENERIC_ONLY = {"regional", "community", "memorial", "general", "county", "university",
                "saint", "st", "mount", "mt", "north", "south", "east", "west", "valley"}
# Words naming a distinct kind of facility. A source name carrying one of these
# never matches a CMS hospital whose name lacks it (e.g. "... Long Term Acute
# Care at Warm Springs" must not attach to "Warm Springs Medical Center").
FACILITY_KIND_WORDS = {
    "specialty", "rehab", "rehabilitation", "behavioral", "psychiatric", "mental",
    "children", "childrens", "women", "womens", "ltac", "ltach", "long", "term",
    "surgical", "surgery", "heart", "cancer", "orthopedic", "orthopaedic", "emergency",
    "er", "ed", "eye", "spine", "joint", "kidney", "transplant", "hospice", "nursing",
    "wellness", "recovery", "addiction", "freestanding", "outpatient", "ambulatory",
}
ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
CCN_RE = re.compile(r"^[0-9A-Z]{6}$")


def name_tokens(name: str) -> frozenset[str]:
    s = (name or "").lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"\bst\.?\b", "saint", s)
    s = re.sub(r"\bmt\.?\b", "mount", s)
    s = re.sub(r"'s\b", "", s)
    s = re.sub(r"^\s*\d{2}-?\d{7}\s*", " ", s)  # leading EIN as in "26-1214372 NEA Baptist"
    toks = re.sub(r"[^a-z0-9\s]", " ", s).split()
    return frozenset(t for t in toks if t not in NAME_STOPWORDS and not t.isdigit() and len(t) > 1)


def distinctive(tokens: frozenset[str]) -> bool:
    return bool(tokens - GENERIC_ONLY)


def kind_compatible(source_tokens: frozenset[str], cms_tokens: frozenset[str]) -> bool:
    return (source_tokens & FACILITY_KIND_WORDS) <= cms_tokens


def norm_city(city: str | None) -> str | None:
    if not city:
        return None
    c = re.sub(r"[^a-z\s]", " ", city.lower())
    c = re.sub(r"\bsaint\b", "st", c)
    c = re.sub(r"\bst\b", "st", c)
    c = re.sub(r"\bft\b", "fort", c)
    c = re.sub(r"\bmt\b", "mount", c)
    c = " ".join(c.split())
    if not c or c in ("not provided", "none", "unknown", "n a"):
        return None
    return c


def load_hospitals() -> list[dict]:
    return json.loads(HOSPITALS_JSON.read_text(encoding="utf-8"))


def blocked_reason(hospital: dict, proc_id: str, codes: CodeIndex) -> str | None:
    htype = hospital.get("hospitalType") or ""
    if htype in NON_SURGICAL_TYPES and codes.category(proc_id) != IMAGING_CATEGORY:
        return "procedure_incompatible_with_hospital_type"
    if htype in NO_INPATIENT_TYPES and codes.scope(proc_id) == "inpatient_stay":
        return "procedure_incompatible_with_hospital_type"
    return None


class StrictHospitalMatcher:
    """Attach a source facility to exactly one CMS hospital, or to none.

    Rules (first that applies):
      1. ccn: the source states a CCN that exists in hospitals.json.
      2. name+city: identical distinctive name tokens and the same state and
         city (or ZIP).
      4. name-subset+city: one name's tokens contain the other's, >= 2 shared
         tokens (one non-generic), same state and city/ZIP, unique.
      3. name+state: identical distinctive name tokens, same state, the source
         gives no city/ZIP at all, and exactly one hospital in the state has that
         name.
    Subset/fuzzy matches are never accepted. Ambiguity -> no match.
    """

    def __init__(self, hospitals: list[dict]):
        self.by_ccn = {h["cmsProviderId"]: h for h in hospitals if h.get("cmsProviderId")}
        self.by_state_name: dict[tuple[str, frozenset], list[dict]] = defaultdict(list)
        self.by_state: dict[str, list[dict]] = defaultdict(list)
        for h in hospitals:
            st = (h.get("state") or "").upper()
            self.by_state[st].append(h)
            toks = name_tokens(h.get("name", ""))
            if st and toks:
                self.by_state_name[(st, toks)].append(h)

    def match(self, names: list[str], state: str, cities: set[str], zips: set[str],
              ccn: str | None = None) -> tuple[dict | None, str]:
        if ccn and ccn in self.by_ccn:
            return self.by_ccn[ccn], "ccn"
        state = (state or "").upper().strip()
        if not state:
            return None, "no_state"
        cities = {c for c in (norm_city(c) for c in cities) if c}
        found: dict[str, tuple[dict, str]] = {}
        saw_name = False
        for name in names:
            toks = name_tokens(name)
            if not toks or not distinctive(toks):
                continue
            cands = self.by_state_name.get((state, toks), [])
            if not cands:
                continue
            saw_name = True
            if cities or zips:
                hits = [
                    h for h in cands
                    if (norm_city(h.get("city")) in cities) or ((h.get("zip") or "")[:5] in zips)
                ]
                for h in hits:
                    found.setdefault(h["cmsProviderId"], (h, "name+city"))
            elif len(cands) == 1:
                h = cands[0]
                found.setdefault(h["cmsProviderId"], (h, "name+state"))
        if not found and (cities or zips):
            # 4. one name's distinctive tokens contain the other's (at least two shared
            #    tokens, one of them not generic), same state AND same city/ZIP, unique.
            local = [
                h for h in self.by_state.get(state, [])
                if (norm_city(h.get("city")) in cities) or ((h.get("zip") or "")[:5] in zips)
            ]
            for name in names:
                toks = name_tokens(name)
                if not toks:
                    continue
                for h in local:
                    ht = name_tokens(h.get("name", ""))
                    shared = toks & ht
                    if (len(shared) >= 2 and distinctive(shared) and (toks <= ht or ht <= toks)
                            and kind_compatible(toks, ht)):
                        found.setdefault(h["cmsProviderId"], (h, "name-subset+city"))
        if len(found) == 1:
            return next(iter(found.values()))
        if len(found) > 1:
            return None, "ambiguous_hospital_match"
        if saw_name:
            return None, "name_matched_but_city_or_uniqueness_failed"
        return None, "no_strict_name_match"


# ---------------------------------------------------------------- quarantine

class Quarantine:
    def __init__(self, sample_size: int = 20):
        self.counts: Counter = Counter()
        self.samples: dict[str, list[dict]] = defaultdict(list)
        self.sample_size = sample_size

    def add(self, reason: str, record: dict, n: int = 1) -> None:
        self.counts[reason] += n
        if len(self.samples[reason]) < self.sample_size:
            self.samples[reason].append(record)

    def merge(self, other: "Quarantine") -> None:
        for reason, n in other.counts.items():
            self.counts[reason] += n
        for reason, recs in other.samples.items():
            for r in recs:
                if len(self.samples[reason]) < self.sample_size:
                    self.samples[reason].append(r)

    def to_dict(self) -> dict:
        return {
            "counts": dict(sorted(self.counts.items())),
            "samples": {k: self.samples[k] for k in sorted(self.samples)},
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "Quarantine":
        q = cls()
        if d:
            q.counts.update(d.get("counts") or {})
            for k, v in (d.get("samples") or {}).items():
                q.samples[k] = list(v)
        return q


def write_quarantine_section(section: str, q: Quarantine, extra: dict | None = None) -> None:
    """Replace one source's section of data/cms/quarantine.json, keep the others."""
    doc = read_json(QUARANTINE_JSON, {}) or {}
    sections = doc.get("sections") or {}
    payload = q.to_dict()
    if extra:
        payload.update(extra)
    sections[section] = payload
    total: Counter = Counter()
    for s in sections.values():
        total.update(s.get("counts") or {})
    out = {
        "description": (
            "Rows and source lines excluded from the published price files, by reason. "
            "'line:' reasons are individual MRF lines/payer rates; 'row:' reasons are "
            "whole hospital+procedure price rows. Up to 20 samples per reason."
        ),
        "totalsByReason": dict(sorted(total.items())),
        "sections": {k: sections[k] for k in sorted(sections)},
    }
    atomic_write_text(QUARANTINE_JSON, dump_json(out))


# ---------------------------------------------------------------- row checks

def order_row(row: dict) -> dict:
    out = {k: row.get(k) for k in ROW_KEY_ORDER if k in row}
    for k in sorted(row):
        if k not in out:
            out[k] = row[k]
    return out


def contract_problems(row: dict, codes: CodeIndex, hospitals_by_id: dict[str, dict]) -> list[str]:
    """Return reasons a finished row breaks the output contract (empty if fine)."""
    probs: list[str] = []
    pid = row.get("procedureId")
    if pid not in codes.by_id:
        return ["unknown_procedure"]
    h = hospitals_by_id.get(row.get("hospitalId"))
    if not h:
        probs.append("unknown_hospital")
    if FORBIDDEN_FIELDS & set(row):
        probs.append("forbidden_estimate_field")
    if row.get("priceSource") not in VALID_SOURCES:
        probs.append("bad_price_source")
    if row.get("scope") != codes.scope(pid):
        probs.append("scope_not_canonical")
    if not parse_iso_date(row.get("priceVintage")) or row.get("priceVintage") != parse_iso_date(row.get("priceVintage")):
        probs.append("missing_or_bad_vintage")
    mrf = row.get("mrfUrl")
    if mrf is not None and (not str(mrf).startswith("https://") or "oria-data.trillianthealth.com" in str(mrf)):
        probs.append("bad_mrf_url")
    if row.get("cashMedian") is None and row.get("negotiatedMedian") is None:
        probs.append("no_cash_or_negotiated_median")
    floor = codes.floor(pid)
    for k in ("cashLow", "cashMedian", "cashHigh", "negotiatedLow", "negotiatedMedian", "negotiatedHigh", "grossCharge"):
        v = row.get(k)
        if v is not None and valid_amount(v, floor if k != "grossCharge" else 0) is None:
            probs.append(f"out_of_bounds:{k}")
    if h:
        b = blocked_reason(h, pid, codes)
        if b:
            probs.append(b)
    return probs


# ---------------------------------------------------------------- line rules

def line_scope_problem(scope: str, setting, billing, modifiers) -> str | None:
    """Why an MRF line is outside the procedure's canonical scope (None = in scope)."""
    if norm_label(modifiers):
        return "line:has_modifier"
    setting = norm_label(setting)
    billing = norm_label(billing)
    if scope == "inpatient_stay":
        if setting not in (None, "inpatient", "both") or billing == "professional":
            return "line:scope_mismatch"
        return None
    if billing == "professional" or setting == "inpatient":
        return "line:scope_mismatch"
    if billing is None:
        return "line:billing_class_missing"
    if billing != "facility" or setting not in ("outpatient", "both"):
        return "line:setting_missing_or_unrecognised"
    return None


def aggregate_lines(lines: list[dict], floor: float, q: "Quarantine") -> dict:
    """Aggregate accepted MRF lines for one hospital + procedure.

    Each line: {"cash", "gross", "rates": [{"payer","plan","dollar","methodology"}], "sample"}.
    cash = published discounted cash only; negotiated = dollar payer/plan rates
    (median per payer+plan, then median/min/max across plans).
    """
    cash_vals: list[float] = []
    gross_vals: list[float] = []
    plan_rates: dict[tuple[str, str], list[float]] = defaultdict(list)
    for ln in lines:
        for key, target, fl in (("cash", cash_vals, floor), ("gross", gross_vals, 0.0)):
            v = ln.get(key)
            if v is None or v != v:
                continue
            prob = amount_problem(v, fl)
            if prob:
                q.add(f"line:{key}_{prob}", {**ln["sample"], "value": v})
            else:
                target.append(float(v))
        for r in ln.get("rates") or []:
            meth = norm_label(r.get("methodology"))
            v = r.get("dollar")
            if v is None:
                continue
            if meth in EXCLUDED_METHODOLOGIES:
                q.add("line:payer_rate_excluded_methodology",
                      {**ln["sample"], "payer": r.get("payer"), "methodology": meth, "value": v})
                continue
            prob = amount_problem(v, floor)
            if prob:
                q.add(f"line:payer_rate_{prob}",
                      {**ln["sample"], "payer": r.get("payer"), "plan": r.get("plan"), "value": v})
                continue
            key = ((r.get("payer") or "").strip().lower(), (r.get("plan") or "").strip().lower())
            plan_rates[key].append(float(v))
    plan_medians = sorted(statistics.median(v) for v in plan_rates.values())
    return {
        "cashLow": round(min(cash_vals)) if cash_vals else None,
        "cashMedian": median_round(cash_vals),
        "cashHigh": round(max(cash_vals)) if cash_vals else None,
        "negotiatedLow": round(plan_medians[0]) if plan_medians else None,
        "negotiatedMedian": median_round(plan_medians),
        "negotiatedHigh": round(plan_medians[-1]) if plan_medians else None,
        "payerCount": len(plan_medians) if plan_medians else None,
        "grossCharge": median_round(gross_vals),
        "lineCount": len(lines),
    }
