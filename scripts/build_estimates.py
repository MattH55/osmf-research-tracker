#!/usr/bin/env python3
"""Validate and build the additive PAIS estimate layer.

The core build deliberately does not read data/optional: crosswalks are consumer-side
assumptions and must never alter evidence exports.
"""
from __future__ import annotations
import csv, glob, hashlib, io, json, os, sys
from itertools import combinations
from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COHORTS = os.path.join(ROOT, "data", "cohorts", "*.json")
SCHEMA = os.path.join(ROOT, "data", "pais-estimate.schema.json")
CONTRAST_SCHEMA = os.path.join(ROOT, "data", "pais-contrast.schema.json")
SPECIMEN_SCHEMA = os.path.join(ROOT, "data", "pais-specimen.schema.json")
HPO = os.path.join(ROOT, "data", "vocab", "hpo", "hp-subset.json")
OSMF = os.path.join(ROOT, "data", "vocab", "osmf-ext.yaml")
INSTRUMENTS = os.path.join(ROOT, "data", "vocab", "instruments.yaml")
OUT = {"csv": os.path.join(ROOT, "data", "pais-estimates.csv"), "json": os.path.join(ROOT, "data", "pais-estimates.json"),
       "contrasts": os.path.join(ROOT, "data", "pais-contrasts.csv"), "specimens": os.path.join(ROOT, "data", "pais-specimens.csv"),
       "matrix": os.path.join(ROOT, "data", "pais-comparability.json")}
VOCAB_HTML=os.path.join(ROOT, "vocab.html")

def load(p):
    # Registry .yaml files intentionally use the JSON subset of YAML, avoiding a new runtime dependency.
    with open(p, encoding="utf-8") as f: return json.load(f)

def dump(p, value):
    with open(p, "w", encoding="utf-8", newline="\n") as f: json.dump(value, f, ensure_ascii=False, indent=2); f.write("\n")

def write_csv(p, rows):
    s=io.StringIO(newline=""); w=csv.writer(s, lineterminator="\n"); w.writerows(rows)
    with open(p, "w", encoding="utf-8", newline="") as f: f.write(s.getvalue())

def estimate_id(cid, e):
    bits=[cid, e["construct"], e["instrument"], e["scoring"], e["threshold"], e["t_months"], e["t_anchor"], e["subgroup"], e["denom_type"]]
    raw=json.dumps(bits, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=6).hexdigest()

def threshold_key(e): return json.dumps(e.get("threshold"), sort_keys=True, separators=(",", ":"))
def join_key(e): return (e["construct"], e["instrument"], e["scoring"], threshold_key(e), e["t_bin"], e["t_anchor"])

def validate(cohorts, strict=False):
    validator=Draft202012Validator(load(SCHEMA)); contrast_validator=Draft202012Validator(load(CONTRAST_SCHEMA)); specimen_validator=Draft202012Validator(load(SPECIMEN_SCHEMA)); hpo={t["id"] for t in load(HPO).get("terms", []) if not t.get("obsolete")}
    ext=load(OSMF); osmf={t["id"] for t in ext if t.get("status") == "active"}
    registry={x["id"]: x for x in load(INSTRUMENTS)}
    errors=[]; warnings=[]; seen=set(); uses={}
    for path, c in cohorts:
        status=c.get("estimates_status")
        if status not in ("none", "partial", "complete"): errors.append(f"{path}: invalid estimates_status")
        for e in c.get("estimates", []):
            for err in validator.iter_errors(e): errors.append(f"{path}: estimate schema: {'/'.join(map(str,err.path))}: {err.message}")
            if e.get("construct", "").startswith("HP:") and e.get("construct") not in hpo: errors.append(f"{path}: construct {e.get('construct')} not in pinned HPO subset")
            if e.get("construct", "").startswith("OSMF:") and e.get("construct") not in osmf: errors.append(f"{path}: construct {e.get('construct')} not an active OSMF term")
            inst=e.get("instrument")
            if inst:
                r=registry.get(inst)
                if not r: errors.append(f"{path}: unknown instrument {inst}")
                elif e.get("scoring") not in {s.get("id") for s in r.get("scoring", [])}: errors.append(f"{path}: scoring {e.get('scoring')} not registered for {inst}")
            if e.get("numerator", 0) > e.get("denominator", 0): errors.append(f"{path}: numerator exceeds denominator")
            expected=estimate_id(c["id"], e)
            if e.get("estimate_id") != expected: errors.append(f"{path}: estimate_id must be generated deterministic hash {expected}")
            if e.get("estimate_id") in seen: errors.append(f"{path}: duplicate estimate_id {e.get('estimate_id')}")
            seen.add(e.get("estimate_id")); uses.setdefault(e.get("construct"), set()).add(c["id"])
            if strict and e.get("harmonization_distance") == 3: warnings.append(f"{path}: estimate {e['estimate_id']} has harmonization_distance 3")
        if strict and status == "none": warnings.append(f"{path}: estimates_status is none")
        for x in c.get("contrasts", []):
            for err in contrast_validator.iter_errors(x): errors.append(f"{path}: contrast schema: {'/'.join(map(str,err.path))}: {err.message}")
        for x in c.get("specimens", []):
            for err in specimen_validator.iter_errors(x): errors.append(f"{path}: specimen schema: {'/'.join(map(str,err.path))}: {err.message}")
    for term in ext:
        if not term.get("justification") or not term.get("mappings"): errors.append(f"OSMF {term.get('id')}: mapping and justification required")
    if strict:
        for construct, cs in uses.items():
            if len(cs) == 1: warnings.append(f"construct {construct} used by one cohort")
    return errors, warnings

def matrix(cohorts):
    out=[]
    for (_, a), (_, b) in combinations(sorted(cohorts, key=lambda x:x[1]["id"]), 2):
        aes=a.get("estimates", []); bes=b.get("estimates", []); keys=[]
        for x in aes:
            for y in bes:
                if join_key(x)==join_key(y): grade="exact"
                elif (x["construct"],x["instrument"],x["t_bin"],x["t_anchor"]) == (y["construct"],y["instrument"],y["t_bin"],y["t_anchor"]): grade="instrument_match"
                elif (x["construct"],x["t_bin"],x["t_anchor"]) == (y["construct"],y["t_bin"],y["t_anchor"]): grade="construct_match"
                else: continue
                keys.append({"key": list(join_key(x)), "grade": grade})
        out.append({"cohorts": [a["id"], b["id"]], "joinable": keys, "grade": max((x["grade"] for x in keys), key=lambda z:["none","construct_match","instrument_match","exact"].index(z), default="none")})
    return out

def render_vocab():
    hpo=load(HPO); ext=load(OSMF)
    rows=[]
    for t in ext:
        maps="; ".join(f"{m.get('predicate')}: {m.get('target')}" for m in t.get('mappings',[]))
        rows.append(f"<tr><td>{t.get('id')}</td><td>{t.get('label')}</td><td>{t.get('definition')}</td><td>{maps}</td><td>{t.get('justification')}</td></tr>")
    body="<h1>PAIS vocabulary</h1><p>This page documents the pinned HPO subset and public OSMF extension justifications.</p>"
    body+=f"<p>HPO release: {hpo.get('release')}; {len(hpo.get('terms',[]))} shipped terms.</p>"
    body+=("<h2>OSMF extensions</h2><table><tr><th>ID</th><th>Label</th><th>Definition</th><th>HPO mappings</th><th>Justification</th></tr>"+"".join(rows)+"</table>") if rows else "<h2>OSMF extensions</h2><p>No extension terms have been added.</p>"
    with open(VOCAB_HTML,"w",encoding="utf-8",newline="\n") as f:f.write("<!doctype html><meta charset='utf-8'><title>PAIS vocabulary</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}</style>"+body)

def main():
    strict="--strict" in sys.argv; check="--check" in sys.argv
    cohorts=[(p, load(p)) for p in sorted(glob.glob(COHORTS))]
    errors,warnings=validate(cohorts, strict)
    if errors:
        print("ESTIMATE VALIDATION FAILED:", *["  - "+e for e in errors], sep="\n", file=sys.stderr); raise SystemExit(1)
    for w in warnings: print("warning: "+w)
    if check: return
    estimates=[dict(e, cohort_id=c["id"]) for _,c in cohorts for e in c.get("estimates", [])]
    contrasts=[dict(x, cohort_id=c["id"]) for _,c in cohorts for x in c.get("contrasts", [])]
    specimens=[dict(x, cohort_id=c["id"]) for _,c in cohorts for x in c.get("specimens", [])]
    dump(OUT["json"], {"schema_version":"1.1.0", "estimates":estimates})
    header=["estimate_id","cohort_id","construct","verbatim","instrument","scoring","threshold","t_months","t_bin","t_anchor","numerator","denominator","denom_type","subgroup","derivation","harmonization_distance","source"]
    write_csv(OUT["csv"], [header]+[[json.dumps(e.get(k), ensure_ascii=False, sort_keys=True) if isinstance(e.get(k),(dict,list)) else e.get(k) for k in header] for e in estimates])
    write_csv(OUT["contrasts"], [["cohort_id","contrast"]]+[[x["cohort_id"],json.dumps(x,ensure_ascii=False,sort_keys=True)] for x in contrasts])
    write_csv(OUT["specimens"], [["cohort_id","specimen"]]+[[x["cohort_id"],json.dumps(x,ensure_ascii=False,sort_keys=True)] for x in specimens])
    dump(OUT["matrix"], {"schema_version":"1.1.0", "pairs":matrix(cohorts)})
    render_vocab()
    print(f"Built estimate layer: {len(estimates)} estimates, {len(contrasts)} contrasts, {len(specimens)} specimens.")
if __name__ == "__main__": main()
