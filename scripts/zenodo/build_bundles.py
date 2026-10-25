#!/usr/bin/env python3
"""Build Zenodo deposit bundles for the OSMF datasets.

Each record is built from an explicit allow-list (see RECORDS), never a whole
directory. Output goes to dist/zenodo/<record-id>/ (git-ignored):

    data files (folders with many files are zipped), README.md, CHECKSUMS.sha256

Metadata for the deposit lives in deposit/zenodo/<record-id>.metadata.json and
is written by this script on first run (edit it there afterwards; it is not
overwritten unless --rewrite-metadata is passed).

    python scripts/zenodo/build_bundles.py                 # first batch: R1 R2 R3 R4
    python scripts/zenodo/build_bundles.py --record R1
    python scripts/zenodo/build_bundles.py --reserved-doi R1=10.5281/zenodo.123  # stamp a DOI

Rules: see ZENODO_DEPOSIT_AGENT_TASK.md. Builds refuse to run from a dirty
working tree for the files they include, so every bundle cites a real commit.
"""
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import json
import shutil
import subprocess
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist" / "zenodo"
META = ROOT / "deposit" / "zenodo"
SITE = "https://research.opensourcemed.info"
VERSION = date.today().strftime("%Y.%m")

CREATORS = [{"name": "Halma, Matthew T. J.", "affiliation": "Open Source Medicine Foundation",
             "orcid": "0000-0003-2487-0636"}]
CONTRIBUTORS = [{"name": "Open Source Medicine Foundation", "type": "HostingInstitution"}]
NOT_ADVICE = "Research information, not medical advice."

SOURCES = {
    "pubmed": ("https://pubmed.ncbi.nlm.nih.gov/", "PubMed (NCBI/NLM)"),
    "ctgov": ("https://clinicaltrials.gov/", "ClinicalTrials.gov (US National Library of Medicine)"),
    "gwas": ("https://www.ebi.ac.uk/gwas/", "NHGRI-EBI GWAS Catalog"),
    "chembl": ("https://www.ebi.ac.uk/chembl/", "ChEMBL (EMBL-EBI), CC BY-SA 3.0"),
    "opentargets": ("https://platform.opentargets.org/", "Open Targets Platform, CC0"),
    "dgidb": ("https://dgidb.org/", "DGIdb"),
}

BIOMARKER_NON_ATLAS = {"agent-discovery.json", "commercial-links.json", "consumable-links.json",
                       "intervention-links.json", "outcome-ontology.json", "search-index.json",
                       "trial-links.json"}
POST_VIRAL = ["long-covid", "pacvs", "me-cfs", "lyme", "gulf-war-illness", "mcas", "pots", "other-post-viral"]

RECORDS = {
    "R1": {
        "title": "PAIS Cohort Database: post-acute infection syndrome cohorts, observations and estimates",
        "landing": "/pais-cohorts.html",
        "license": "cc-by-4.0",
        "keywords": ["post-acute infection syndromes", "PAIS", "Long COVID", "ME/CFS", "cohort studies",
                     "post-infectious illness", "evidence synthesis", "open data"],
        "sources": ["pubmed"],
        "files": ["data/pais-*.csv", "data/pais-*.json", "data/ref/*.json",
                  "pais-cohort-database-spec.md", "pais-severity-harmony-v1.md",
                  "pais-susceptibility-factors-spec.md"],
        "zip": {"cohorts.zip": ["data/cohorts/*.json"]},
        "summary": ("Cohort-level records of post-acute infection syndrome (PAIS) studies across pathogens "
                    "(SARS-CoV-2, EBV, Giardia, Borrelia and others): study design, enrolment, follow-up, "
                    "specimens, and harmonised observations, estimates, contrasts and predictors extracted from "
                    "published papers. All values are study-level aggregates; no individual-level data."),
        "notes": ("Supersedes the git tag pais-v1.1 (July 2026). Short verbatim phrases in "
                  "measure_verbatim are quoted from the cited papers (longest: one sentence)."),
    },
    "R2": {
        "title": "OSMF Biomarker Atlases: biomarkers reported in patients versus controls",
        "landing": "/biomarker-atlas.html",
        "license": "cc-by-4.0",
        "keywords": ["biomarkers", "Long COVID", "ME/CFS", "PACVS", "Lyme disease", "Gulf War Illness",
                     "chronic disease", "GWAS", "open data"],
        "sources": ["pubmed", "gwas"],
        "files": ["biomarkers.schema.json", "data/genetics/*"],
        "zip": {"biomarker-atlases.zip": ["data/biomarkers/*.json"]},
        "exclude": BIOMARKER_NON_ATLAS,
        "summary": ("Per-condition biomarker atlases: markers reported in patients versus controls, with "
                    "direction of change, specimen, assay and the source publication for each finding, plus "
                    "genetic correlates (loci, variants, genes) from the GWAS Catalog."),
        "notes": "Validated against biomarkers.schema.json at build time.",
    },
    "R3": {
        "title": "Post-viral illness literature index: Long COVID, PACVS, ME/CFS, Lyme, Gulf War Illness, MCAS and POTS",
        "landing": "/post-viral-illness.html",
        "license": "cc-by-4.0",
        "keywords": ["Long COVID", "PACVS", "ME/CFS", "Lyme disease", "Gulf War Illness", "MCAS", "POTS",
                     "literature index", "post-viral illness"],
        "sources": ["pubmed"],
        "files": ["data/post-viral-illness.json", "post-viral-illness.schema.json"],
        "strip_abstracts": [f"data/{n}.json" for n in POST_VIRAL],
        "summary": ("Per-condition indexes of peer-reviewed studies on post-viral illnesses, retrieved from "
                    "PubMed (PMID, title, publication date, journal, authors, link), plus the OSMF cross-condition "
                    "reference file describing each illness (triggers, onset, core features, epidemiology, "
                    "mechanisms, diagnosis, treatments studied, references)."),
        "notes": ("PubMed abstracts present in the live tracker files are removed from this deposit because "
                  "they are copyrighted by their publishers; follow the PMID to read them. "
                  "post-viral-illness.schema.json describes post-viral-illness.json only; the per-condition "
                  "files are documented below."),
    },
    "R4": {
        "title": "Clinical trials snapshot and treatment ontology for post-viral and chronic conditions",
        "landing": "/trials/index.html",
        "license": "cc-by-4.0",
        "keywords": ["clinical trials", "ClinicalTrials.gov", "treatment ontology", "drug repurposing",
                     "Long COVID", "chronic disease"],
        "sources": ["ctgov"],
        "files": ["data/clinical_trials/clinical_trials_current.json", "data/clinical_trials/treatment-ontology.json"],
        "rename": {"data/clinical_trials/outcomes-cache.json": "trial-outcomes.json"},
        "summary": ("Snapshot of registered trials tracked by OSMF (registry fields from ClinicalTrials.gov), "
                    "registry outcome measures for the tracked trials, and the OSMF treatment ontology that "
                    "classifies trial interventions (drug, supplement, device, behavioural, comparator)."),
        "notes": "Registry content remains subject to ClinicalTrials.gov terms; cite the NCT number.",
    },
}


def sh(*args: str) -> str:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def expand(patterns: list[str], exclude: set[str] = frozenset()) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        for p in sorted(glob.glob(str(ROOT / pat))):
            path = Path(p)
            if path.is_file() and path.name not in exclude and "/cache/" not in path.as_posix():
                out.append(path)
    return out


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def assert_clean(paths: list[Path]) -> None:
    dirty = sh("git", "status", "--porcelain", "--", *[rel(p) for p in paths])
    if dirty:
        raise SystemExit(f"refusing to build: uncommitted or untracked files in this record:\n{dirty}")


def strip_abstracts(obj):
    if isinstance(obj, dict):
        return {k: strip_abstracts(v) for k, v in obj.items() if k.lower() != "abstract"}
    if isinstance(obj, list):
        return [strip_abstracts(x) for x in obj]
    return obj


def validate(schema_file: Path, data_files: list[Path]) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return [f"jsonschema not installed; skipped validation against {schema_file.name}"]
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    v = jsonschema.validators.validator_for(schema)(schema)
    errors = []
    for f in data_files:
        e = next(iter(v.iter_errors(json.loads(f.read_text(encoding="utf-8")))), None)
        if e:
            errors.append(f"{f.name}: {e.message[:160]}")
    return errors


def field_list(files: list[Path]) -> list[str]:
    """Top-level and first-record keys of each JSON file, for the README field table."""
    lines = []
    for f in files:
        if f.suffix != ".json":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        top = list(d)[:12] if isinstance(d, dict) else ["(array)"]
        rec = None
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    rec = list(v[0])[:15]
                    break
        lines.append(f"- `{f.name}`: top-level `{', '.join(top)}`" + (f"; record fields `{', '.join(rec)}`" if rec else ""))
    return lines


def readme(rid: str, r: dict, commit: str, contents: list[str], fields: list[str], doi: str | None) -> str:
    lic = {"cc-by-4.0": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
           "cc-by-sa-4.0": "Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)"}[r["license"]]
    cite_doi = f"https://doi.org/{doi}" if doi else "(DOI assigned on deposit)"
    src = "\n".join(f"- {SOURCES[s][1]}: {SOURCES[s][0]}" for s in r["sources"])
    return f"""# {r['title']}

{r['summary']}

{NOT_ADVICE}

- **Publisher:** Open Source Medicine Foundation (OSMF), Tallinn, Estonia
- **Creator:** Matthew T. J. Halma (ORCID 0000-0003-2487-0636)
- **Version:** {VERSION}
- **Live version:** {SITE}{r['landing']}
- **Built from:** https://github.com/MattH55/osmf-research-tracker at commit `{commit}`
- **Licence:** {lic}

## How to cite

Halma, M. T. J. ({date.today().year}). *{r['title']}* (Version {VERSION}) [Data set]. Open Source Medicine Foundation. {cite_doi}

## Contents

{chr(10).join(contents)}

## Fields

{chr(10).join(fields) if fields else "See the schema file(s) included in this deposit."}

## Provenance

Compiled by OSMF from:

{src}

Third-party records remain under their original terms. {r.get('notes', '')}

## Integrity

`CHECKSUMS.sha256` lists a SHA-256 hash for every file in this deposit.
"""


def metadata(rid: str, r: dict, commit: str) -> dict:
    related = [{"identifier": f"{SITE}{r['landing']}", "relation": "isDocumentedBy", "resource_type": "other"}]
    related += [{"identifier": SOURCES[s][0], "relation": "isDerivedFrom", "resource_type": "dataset"} for s in r["sources"]]
    related.append({"identifier": f"https://github.com/MattH55/osmf-research-tracker/tree/{commit}",
                    "relation": "isSupplementTo", "resource_type": "software"})
    desc = (f"<p>{r['summary']}</p><p>{r.get('notes', '')}</p>"
            f"<p>Live, daily-updated version: <a href=\"{SITE}{r['landing']}\">{SITE}{r['landing']}</a>. "
            f"Built from commit {commit} of the OSMF Research Tracker.</p><p>{NOT_ADVICE}</p>")
    return {
        "upload_type": "dataset",
        "title": r["title"],
        "description": desc,
        "creators": copy.deepcopy(CREATORS),
        "contributors": copy.deepcopy(CONTRIBUTORS),
        "access_right": "open",
        "license": r["license"],
        "keywords": r["keywords"],
        "related_identifiers": related,
        "version": VERSION,
        "language": "eng",
        "notes": NOT_ADVICE,
        "prereserve_doi": True,
    }


def build(rid: str, args) -> None:
    r = RECORDS[rid]
    exclude = r.get("exclude", set())
    plain = expand(r["files"], exclude)
    zipped = {name: expand(pats, exclude) for name, pats in r.get("zip", {}).items()}
    stripped = expand(r.get("strip_abstracts", []))
    renamed = {ROOT / k: v for k, v in r.get("rename", {}).items()}
    everything = plain + [p for v in zipped.values() for p in v] + stripped + list(renamed)
    assert_clean(everything)
    commit = sh("git", "log", "-1", "--format=%H", "--", *[rel(p) for p in everything])
    out = DIST / rid
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    contents, field_files, report = [], [], []
    for p in plain:
        shutil.copy2(p, out / p.name)
        contents.append(f"- `{p.name}` (from `{rel(p)}`)")
        field_files.append(out / p.name)
    for src, name in renamed.items():
        shutil.copy2(src, out / name)
        contents.append(f"- `{name}` (from `{rel(src)}`)")
        field_files.append(out / name)
    removed = 0
    for p in stripped:
        d = json.loads(p.read_text(encoding="utf-8"))
        before = json.dumps(d).count('"abstract"')
        clean = strip_abstracts(d)
        removed += before
        (out / p.name).write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")
        contents.append(f"- `{p.name}` (from `{rel(p)}`, abstracts removed)")
        field_files.append(out / p.name)
    if stripped:
        leftover = sum((out / p.name).read_text(encoding="utf-8").count('"abstract"') for p in stripped)
        assert leftover == 0, "abstract fields remain after stripping"
        report.append(f"abstract fields removed: {removed}")
    for name, members in zipped.items():
        with zipfile.ZipFile(out / name, "w", zipfile.ZIP_DEFLATED) as z:
            for m in members:
                z.write(m, m.name)
        contents.append(f"- `{name}`: {len(members)} files from `{rel(members[0].parent)}/`")
        field_files.extend(members[:1])

    # schema validation
    if rid == "R1":
        report += validate(ROOT / "data/pais-cohort.schema.json", zipped["cohorts.zip"])
    if rid == "R2":
        report += validate(ROOT / "biomarkers.schema.json", zipped["biomarker-atlases.zip"])
    if rid == "R3":
        report += validate(ROOT / "post-viral-illness.schema.json", [ROOT / "data/post-viral-illness.json"])

    doi = dict(x.split("=", 1) for x in args.reserved_doi).get(rid) if args.reserved_doi else None
    (out / "README.md").write_text(readme(rid, r, commit[:12], contents, field_list(field_files), doi), encoding="utf-8")
    sums = []
    for f in sorted(out.iterdir()):
        if f.name != "CHECKSUMS.sha256":
            sums.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}")
    (out / "CHECKSUMS.sha256").write_text("\n".join(sums) + "\n", encoding="utf-8")

    META.mkdir(parents=True, exist_ok=True)
    mpath = META / f"{rid}.metadata.json"
    if args.rewrite_metadata or not mpath.exists():
        mpath.write_text(json.dumps(metadata(rid, r, commit[:12]), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    size = sum(f.stat().st_size for f in out.iterdir())
    n = len(list(out.iterdir()))
    print(f"{rid}: {n} files, {size / 1e6:.1f} MB, commit {commit[:12]}, licence {r['license']}")
    for line in report:
        print(f"   {line}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", nargs="*", default=["R1", "R2", "R3", "R4"])
    ap.add_argument("--reserved-doi", nargs="*", help="RID=DOI pairs to stamp into README")
    ap.add_argument("--rewrite-metadata", action="store_true")
    args = ap.parse_args()
    for rid in args.record:
        build(rid, args)


if __name__ == "__main__":
    main()
