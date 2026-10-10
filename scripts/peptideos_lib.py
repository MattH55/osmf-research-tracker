"""PeptideOS: data loading, validation and editorial lint.

The rules here are the product (see peptideos/peptideos-build-brief.md §6 and
peptideos/ci-rules.md). Any violation makes `build_peptideos.py` exit
non-zero, so a record with a dose, a vendor, advice or an unsourced
regulatory claim cannot be published.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
PEP = ROOT / "peptideos"
DATA = PEP / "data" / "compounds"
TRIALS = PEP / "data" / "trials"

TIERS = ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"]
TIER_LABEL = {
    "E1": "Multiple adequately powered RCTs, consistent",
    "E2": "At least one adequately powered RCT",
    "E3": "Small, underpowered or conflicting RCTs",
    "E4": "Uncontrolled or non-randomised human trials",
    "E5": "Case reports and case series only",
    "E6": "Animal models only",
    "E7": "In vitro only",
    "E8": "No published evidence of efficacy in any model",
}
TIER_SHORT = {"E1": "established", "E2": "RCT evidence", "E3": "weak RCT evidence", "E4": "uncontrolled human data",
              "E5": "case reports only", "E6": "no human evidence", "E7": "no human or animal evidence",
              "E8": "no evidence"}
SAFETY = {
    "S1": "Large long-term human exposure (post-marketing surveillance)",
    "S2": "Substantial controlled-trial safety data",
    "S3": "Limited human safety data",
    "S4": "Minimal human exposure data",
    "S5": "No human safety data",
}
JURIS = {"US": "United States", "EU": "European Union", "UK": "United Kingdom", "CA": "Canada",
         "AU": "Australia", "JP": "Japan", "CN": "China"}
CLASSES = {"A": "Approved", "B": "Investigational", "C": "Gray market"}
REG_STATUS = {"approved": "Approved", "investigational": "Investigational", "unapproved": "Not approved",
              "503a_category_1": "FDA 503A Category 1", "503a_category_2": "FDA 503A Category 2",
              "withdrawn": "Withdrawn / discontinued"}
WADA = {"prohibited": "Prohibited", "not_prohibited": "Not prohibited", "monitored": "Monitoring programme"}

# Primary-source allowlist for regulatory and sport citations (brief §3, ci-rules Rule 9).
PRIMARY_DOMAINS = (
    "fda.gov", "federalregister.gov", "ecfr.gov", "govinfo.gov", "regulations.gov", "dea.gov",
    "ema.europa.eu", "europa.eu", "eur-lex.europa.eu",
    "gov.uk", "mhra.gov.uk", "legislation.gov.uk", "nice.org.uk",
    "mhraproducts4853.blob.core.windows.net",  # MHRA product-information (SmPC/PAR) document store
    "canada.ca", "gc.ca", "health-products.canada.ca", "laws-lois.justice.gc.ca",
    "tga.gov.au", "legislation.gov.au", "health.gov.au", "pbs.gov.au",
    "pmda.go.jp", "mhlw.go.jp", "nmpa.gov.cn", "gov.cn",
    "clinicaltrials.gov", "wada-ama.org", "web.archive.org", "who.int",
)
# Outbound links anywhere on a compound page must be on this list.
LINK_DOMAINS = PRIMARY_DOMAINS + ("doi.org", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "crossref.org",
                                  "opensourcemed.info", "github.com")


class Violation(Exception):
    pass


def host_ok(url: str, allowed=LINK_DOMAINS) -> bool:
    h = (urlparse(url).hostname or "").lower()
    return any(h == d or h.endswith("." + d) for d in allowed)


# ── editorial lint (brief §6) ────────────────────────────────────────────
UNIT = r"(?:mg|mcg|µg|μg|ug|ng|g|iu|IU|international units|units?|ml|mL|cc)"
LINT = [
    ("no-dosing", re.compile(rf"\b\d+(?:[.,]\d+)?\s?(?:–|-|to)?\s?(?:\d+(?:[.,]\d+)?\s?)?{UNIT}(?:\s?/\s?(?:kg|day|week|dose|d|wk))?\b"),
     "Dose amount. PeptideOS publishes no doses, not even label doses."),
    ("no-dosing-words", re.compile(r"\b(?:dosage|dosing schedule|starting dose|maintenance dose|typical dose|commonly used dose|dose range)\b", re.I),
     "Dosing language."),
    ("no-administration", re.compile(r"\b(?:reconstitut\w*|bacteriostatic|draw(?:ing)? up|on-cycle|off-cycle|cycling|stack(?:ed|ing)? with|peptide stack|loading phase|protocol for|dosing protocol|titrat\w*|self-inject\w*|how to inject)\b", re.I),
     "Administration guidance."),
    ("no-purchase-intent", re.compile(r"\b(?:buy|buying|purchase|where to (?:buy|get)|for sale|vendors?|suppliers?|legit|coupon|discount code|cheap|best price|in stock|order now)\b", re.I),
     "Purchase-intent language."),
    ("no-second-person-advice", re.compile(r"\byou(?:'ll)?\s+(?:should|can|could|may want to|might want to|will need to|need to|must)\b|\b(?:start with|consider taking|try taking)\b", re.I),
     "Advice to the reader; the resource describes, it does not advise."),
    ("no-testimonials", re.compile(r"\b(?:before and after|my experience|users report|anecdotal(?:ly)?|worked for me|I noticed|felt better)\b", re.I),
     "Testimonial or anecdote."),
    ("no-hype", re.compile(r"\b(?:promising|exciting|breakthrough|miracle|game[- ]changer|cutting[- ]edge)\b", re.I),
     "Enthusiasm language."),
    ("no-affiliate", re.compile(r"[?&](?:ref|aff|affiliate|tag|partner)=", re.I),
     "Affiliate parameter."),
]
BENEFIT = re.compile(r"\b(?:promotes?|enhances?|boosts?|heals?|repairs?|restores?|accelerates?|rejuvenat\w*|optimi[sz]es?)\b", re.I)
MODEL = re.compile(r"\b(?:rat|rats|mouse|mice|rodent|murine|in vitro|cell|cells|cultured|animal|animals|dog|dogs|pig|pigs|rabbit|primate|zebrafish|patients|participants|trial|trials|volunteers|in humans|model|models)\b", re.I)
VAGUE_UNKNOWN = re.compile(r"\bmore (?:research|studies) (?:is |are )?(?:needed|required)\b", re.I)


QUOTE_EXEMPT = {"no-dosing-words", "no-hype", "no-purchase-intent", "no-administration", "no-second-person-advice"}


def lint_text(where: str, text: str) -> list[str]:
    """Verbatim regulator quotes and source titles are someone else's words: only dose amounts are checked there."""
    out = []
    if not text:
        return out
    quoted = where.endswith((".quote", ".source_title", ".title"))
    for rid, rx, msg in LINT:
        if quoted and rid in QUOTE_EXEMPT:
            continue
        m = rx.search(text)
        if m:
            out.append(f"{where}: [{rid}] {msg} -> '{m.group(0)}'")
    for sent in re.split(r"(?<=[.;!?])\s+", text):
        m = BENEFIT.search(sent)
        if m and not quoted and not MODEL.search(sent):
            out.append(f"{where}: [no-mechanism-as-benefit] Benefit verb without a named model -> '{m.group(0)}' in '{sent[:90]}'")
    return out


def text_fields(rec: dict):
    """Yield (path, text) for every human-readable string in a record."""
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("source_url", "doi", "url", "nct", "slug", "retrieved", "last_reviewed", "cas", "sequence",
                         "trials_query", "jurisdiction", "status", "tier", "grade", "wada_status", "wada_class", "phase"):
                    continue
                yield from walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            yield path, node
    yield from walk(rec, "")


# ── schema + consistency ─────────────────────────────────────────────────
def as_date(v) -> date | None:
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v), "%Y-%m-%d").date()
    except Exception:
        return None


def validate(rec: dict, fname: str) -> list[str]:
    e = []
    req = ["slug", "names", "class_by_jurisdiction", "what_it_is", "evidence", "safety", "regulatory", "unknowns",
           "reviewer", "last_reviewed"]
    for k in req:
        if k not in rec or rec[k] in (None, "", [], {}):
            e.append(f"{fname}: missing required field '{k}'")
    if e:
        return e
    if rec["slug"] != Path(fname).stem:
        e.append(f"{fname}: slug '{rec['slug']}' does not match file name")
    seq = rec.get("sequence")
    if seq and not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY]+", seq):
        e.append(f"{fname}: sequence must be one-letter codes only (use sequence_note for modifications)")
    for j, c in rec["class_by_jurisdiction"].items():
        if j not in JURIS or (c is not None and c not in CLASSES):
            e.append(f"{fname}: bad class_by_jurisdiction entry {j}: {c}")
    for i, ev in enumerate(rec["evidence"]):
        p = f"{fname}: evidence[{i}]"
        if ev.get("tier") not in TIERS:
            e.append(f"{p}: tier must be E1–E8")
            continue
        for k in ("indication", "summary"):
            if not ev.get(k):
                e.append(f"{p}: missing {k}")
        # counts may be null ("not counted"); when given they must agree with the tier
        rcts, any_h = ev.get("human_rcts"), ev.get("human_trials_any")
        t = ev["tier"]
        if rcts is not None:
            if t == "E1" and rcts < 2: e.append(f"{p}: E1 needs ≥2 human RCTs")
            if t == "E2" and rcts < 1: e.append(f"{p}: E2 needs ≥1 human RCT")
            if t in ("E5", "E6", "E7", "E8") and rcts > 0: e.append(f"{p}: {t} cannot have human RCTs")
            if any_h is not None and rcts > any_h: e.append(f"{p}: human_rcts > human_trials_any")
        if any_h is not None and t in ("E6", "E7", "E8") and any_h > 0: e.append(f"{p}: {t} cannot have human trials")
        if t in ("E5", "E6", "E7", "E8") and (rcts is None or any_h is None) and t != "E5":
            e.append(f"{p}: {t} must state human_rcts: 0 and human_trials_any: 0 explicitly")
        for c in ev.get("citations") or []:
            if not (c.get("doi") or c.get("pmid")) or not c.get("title"):
                e.append(f"{p}: every citation needs a DOI or PMID and its exact title")
        if t in ("E1", "E2", "E3", "E4", "E5", "E6", "E7") and not ev.get("citations"):
            e.append(f"{p}: tier {t} asserts published evidence but cites none")
    sf = rec["safety"]
    if sf.get("grade") not in SAFETY:
        e.append(f"{fname}: safety.grade must be S1–S5")
    for i, s in enumerate(sf.get("known_signals") or []):
        c = s.get("citation") or {}
        if not s.get("signal") or not (c.get("doi") or c.get("pmid") or c.get("url")) or not c.get("title"):
            e.append(f"{fname}: safety.known_signals[{i}] needs signal + cited source with title")
    jur_seen = set()
    for i, r in enumerate(rec["regulatory"]):
        p = f"{fname}: regulatory[{i}]"
        if r.get("jurisdiction") not in JURIS: e.append(f"{p}: bad jurisdiction")
        if r.get("status") not in REG_STATUS: e.append(f"{p}: bad status {r.get('status')}")
        for k in ("detail", "source_url", "quote", "retrieved"):
            if not r.get(k): e.append(f"{p}: missing {k} (no regulatory claim without a dated primary source and quote)")
        if r.get("source_url") and not host_ok(r["source_url"], PRIMARY_DOMAINS):
            e.append(f"{p}: source is not a primary regulator source: {r['source_url']}")
        if r.get("retrieved") and not as_date(r["retrieved"]): e.append(f"{p}: retrieved must be YYYY-MM-DD")
        jur_seen.add(r.get("jurisdiction"))
    sp = rec.get("sport")
    if sp:
        if sp.get("wada_status") not in WADA: e.append(f"{fname}: sport.wada_status invalid")
        if not sp.get("source_url") or not host_ok(sp["source_url"], PRIMARY_DOMAINS): e.append(f"{fname}: sport needs a wada-ama.org source")
    if len(rec["unknowns"]) < 3:
        e.append(f"{fname}: unknowns needs at least 3 specific entries")
    for i, u in enumerate(rec["unknowns"]):
        if VAGUE_UNKNOWN.search(u or ""): e.append(f"{fname}: unknowns[{i}] is a placeholder ('more research needed')")
    for t in rec.get("trials") or []:
        if not re.fullmatch(r"NCT\d{8}", str(t.get("nct", ""))) or not t.get("title"):
            e.append(f"{fname}: trials entries need a valid NCT id and registered title")
    if not as_date(rec.get("last_reviewed")):
        e.append(f"{fname}: last_reviewed must be YYYY-MM-DD")
    for path, txt in text_fields(rec):
        e.extend(lint_text(f"{fname}: {path}", txt))
    for path, txt in text_fields(rec):
        for url in re.findall(r"https?://\S+", txt):
            if not host_ok(url): e.append(f"{fname}: {path}: outbound link outside the allowlist: {url}")
    return e


def load_all() -> tuple[list[dict], list[str]]:
    recs, errs = [], []
    for f in sorted(DATA.glob("*.yaml")):
        try:
            rec = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception as ex:
            errs.append(f"{f.name}: YAML error {ex}")
            continue
        errs.extend(validate(rec, f.name))
        rec["_file"] = f.name
        recs.append(rec)
    return recs, errs


def best_tier(rec: dict) -> str:
    return min((ev["tier"] for ev in rec["evidence"]), key=TIERS.index)


def worst_tier(rec: dict) -> str:
    return max((ev["tier"] for ev in rec["evidence"]), key=TIERS.index)


def main_class(rec: dict) -> str:
    """Display class: A if approved anywhere tracked, else B if anywhere B, else C."""
    vals = {v for v in rec["class_by_jurisdiction"].values() if v}
    return "A" if "A" in vals else ("B" if "B" in vals else "C")
