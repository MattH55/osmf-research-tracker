#!/usr/bin/env python3
"""Re-derive the alteration tables of the published RepurpOS disease pages with
the provenance fixes of 2026-10-15, without re-running the whole pipeline.

What it does, per published page (data/disease-intelligence/<slug>.json):

1. Identifiers: applies the verified corrections in IDENTIFIER_CORRECTIONS
   (wrong MONDO IDs that came from an OxO cross-mapping overriding the Open
   Targets hit); replaces every ORPHA ID by the Orphanet cross-reference of the
   disease's MONDO class when its Orphanet label names the disease (the old
   ORPHA IDs were first-hit text-search results, e.g. ADHD -> 1q21.1
   microduplication syndrome), else drops it; drops EFO IDs whose label does
   not name the disease.
2. Open Targets rows: for corrected diseases the top-100 associated targets are
   re-fetched for the right ID; for all others the current OT association score
   is attached to the stored genes. Evidence = "OT score x.xx" (no tier).
3. HPO rows: replaced by the phenotypes annotated directly to the disease's
   MONDO class (Monarch v3, direct=true); descendant-subtype phenotypes go.
4. ClinicalTrials.gov rows: re-typed T "Trial outcome measure".
5. Writes the JSON back and splices the re-rendered identifiers line, overview
   card and alterations section into the published HTML page (the rest of the
   page was post-processed by other scripts and is left untouched).

A full pipeline re-run (main.py --web --html) gives the same alteration tables
because the adapters now implement the same rules (clinical.get_hpo_phenotypes,
molecular._open_targets_genes, score.score_alterations, normalize.*).

Usage:  python -m disease_pipeline.refresh_alteration_provenance [--slugs a,b] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import html as html_lib
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.adapters import clinical, molecular, score  # noqa: E402
from disease_pipeline.adapters.normalize import _ols_term, label_matches  # noqa: E402
from disease_pipeline.http_util import default_session  # noqa: E402
from disease_pipeline.models import Alteration, AlterationType, DiseaseIdentifiers, EvidenceTier  # noqa: E402
from disease_pipeline.output.generate_html import build_html  # noqa: E402
from disease_pipeline.output.web_export import TYPE_LABELS, _export_alteration, _tier_sort_key_alt  # noqa: E402
from disease_pipeline.published_conditions import EXCLUDED_SLUGS, is_publishable  # noqa: E402

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"
MANIFEST = Path(__file__).parent / "seeds" / "alteration_provenance_manifest.json"

log = logging.getLogger(__name__)

# Verified 2026-10-15 against OLS4 (MONDO/EFO labels, synonyms, xrefs) and the
# Open Targets / Monarch entity endpoints. `None` = deliberately unset.
IDENTIFIER_CORRECTIONS: dict[str, dict] = {
    "sarcopenia": {
        "ids": {"efo_id": "EFO_1000653", "mesh_id": "D055948"},
        "was": "MONDO:0002331 (nephrosis)",
        "note": "No MONDO class for sarcopenia; EFO:1000653 'sarcopenia' (indexed by Open Targets). "
        "No HPO rows: Monarch annotates MONDO diseases only. UMLS C1837640 dropped (unverified).",
    },
    "osteoporosis": {
        "ids": {"mondo_id": "MONDO:0005298", "mesh_id": "D010024", "umls_cui": "C0029456"},
        "was": "MONDO:0005291 (brain aneurysm)",
    },
    "anxiety": {
        "ids": {"mondo_id": "MONDO:0005618", "mesh_id": "D001008", "umls_cui": "C0003469"},
        "was": "MONDO:0005090 (schizophrenia)",
        "note": "MONDO:0005618 'anxiety disorder'; UMLS C0003467 (anxiety, the symptom) replaced by C0003469 (anxiety disorders).",
    },
    "age-related-macular-degeneration": {
        "ids": {"mondo_id": "MONDO:0005150", "efo_id": "EFO_0001365", "mesh_id": "D008268", "umls_cui": "C0242383"},
        "was": "MONDO:0001208 (acute respiratory failure); EFO_0001369 (vertebral column structure)",
    },
    "pots": {
        "ids": {"mondo_id": "MONDO:0001315", "mesh_id": "D054972"},
        "was": "MONDO:0100242 (glioma susceptibility)",
        "note": "MONDO has no class labelled POTS: MONDO:0001315 is labelled 'orthostatic intolerance' and carries "
        "'postural orthostatic tachycardia syndrome' and 'POTS' as exact synonyms (MONDO:0011479 is only the "
        "monogenic NET-deficiency form). UMLS C2931185 dropped (unverified).",
    },
    "mcas": {
        "ids": {"mondo_id": "MONDO:0100004", "mesh_id": "D000090267", "umls_cui": "C5200989"},
        "was": "MONDO:0800103 (COACH syndrome 1); UMLS C5680519",
        "note": "MONDO:0100004 'mast cell activation syndrome' is not indexed by Open Targets, so no gene rows.",
    },
    "measles": {
        "ids": {"mondo_id": "MONDO:0004619", "mesh_id": "D008457", "umls_cui": "C0025007"},
        "was": "MONDO:0005850 (milker's nodule)",
    },
    "schizophrenia": {
        "ids": {"mondo_id": "MONDO:0005090", "umls_cui": "C0036341"},
        "was": "MONDO:0005154 (liver disorder)",
    },
    "post-acute-covidvaccination-syndrome": {
        "ids": {"mondo_id": "MONDO:0100233", "mesh_id": "D000086382"},
        "was": "MONDO:0100096 (COVID-19, the acute infection); EFO_1002048; UMLS C5397822",
        "note": "MONDO:0100233 'long COVID-19'. Post-acute COVID-vaccination syndrome has no ontology class.",
    },
    "obesity": {
        "ids": {"mondo_id": "MONDO:0011122"},
        "was": "Open Targets ID HP_0001513 (HPO phenotype 'Obesity', no longer an Open Targets disease in release 26.09); ORPHA:293987 (ROHHAD syndrome)",
        "note": "MONDO:0011122 'obesity disorder' (exact synonym 'obesity'); Open Targets top-100 re-fetched for it.",
    },
}

# EFO cross-references whose label differs from the page name but which were
# checked by hand and kept.
EFO_ACCEPTED = {"EFO_0000180": "HIV-1 infection (page: HIV/AIDS)"}

_ORPHA_RE = re.compile(r"^Orphanet:(\d+)$")


async def _mondo_term(mondo_id: str, session) -> dict:
    return await _ols_term("mondo", "http://purl.obolibrary.org/obo/" + mondo_id.replace(":", "_"), session)


def _xrefs(term: dict) -> list[str]:
    raw = (term.get("annotation") or {}).get("database_cross_reference") or []
    return [x for x in raw if isinstance(x, str)]


async def _verified_orpha(names: list[str], mondo_term: dict, session) -> str | None:
    """Orphanet xref of the MONDO class whose own label names the disease."""
    targets = [n for n in names if n] + [mondo_term.get("label") or ""] + list(mondo_term.get("synonyms") or [])
    for x in _xrefs(mondo_term):
        m = _ORPHA_RE.match(x)
        if not m:
            continue
        ordo = await _ols_term("ordo", f"http://www.orpha.net/ORDO/Orphanet_{m.group(1)}", session)
        if any(label_matches(t, ordo.get("label"), ordo.get("synonyms")) for t in targets if t):
            return f"ORPHA:{m.group(1)}"
    return None


async def _efo_ok(efo_id: str, names: list[str], session) -> bool:
    if not efo_id.startswith("EFO_") or efo_id in EFO_ACCEPTED:
        return True  # HP_/Orphanet_ IDs used by Open Targets as disease IDs
    term = await _ols_term("efo", f"http://www.ebi.ac.uk/efo/{efo_id}", session)
    return any(label_matches(n, term.get("label"), term.get("synonyms")) for n in names if n)


def _to_alteration(a: dict) -> Alteration:
    return Alteration(
        canonical_id=a["canonical_id"],
        name=a["name"],
        alteration_type=AlterationType(a["type"]),
        subtype=a["subtype"],
        direction=a.get("direction"),
        frequency_label=a.get("frequency_label"),
        frequency_pct=a.get("frequency_pct"),
        sources=a.get("sources") or [],
        source_ids=a.get("source_ids") or {},
        evidence_tier=EvidenceTier(a.get("evidence_tier", "C")),
        pubmed_count=a.get("pubmed_count") or 0,
        definition=a.get("definition"),
        association_score=a.get("association_score"),
    )


def _block(pattern: str, text: str) -> re.Match | None:
    ms = list(re.finditer(pattern, text, re.S))
    return ms[0] if len(ms) == 1 else None


SPLICES = [
    ("overview", r'<div class="overview-card">.*?<p class="meta-line">Sources:.*?</p>\s*</div>'),
    ("alterations", r'<p class="meta-line">Identifiers:.*?<section id="alterations">.*?</section>'),
]


def splice_html(live: str, rendered: str, old_hero: str, new_hero: str) -> tuple[str, list[str]]:
    done = []
    for name, pat in SPLICES:
        a, b = _block(pat, live), _block(pat, rendered)
        if a and b:
            live = live[: a.start()] + b.group(0) + live[a.end():]
            done.append(name)
    if old_hero != new_hero:
        for old, new in ((old_hero, new_hero), (html_lib.escape(old_hero), html_lib.escape(new_hero))):
            if old in live:
                live = live.replace(old, new)
                done.append("hero")
    return live, done


async def refresh_page(data: dict, session, *, ot_release: str | None, today: str) -> dict:
    slug = data["slug"]
    name = data["condition"]["name"]
    names = [name, data["condition"].get("shortName") or "", re.sub(r"\s*\([^)]*\)", "", name)]
    ids = dict(data.get("identifiers") or {})
    report: dict = {"slug": slug, "identifiers_before": dict(ids)}

    corr = IDENTIFIER_CORRECTIONS.get(slug)
    if corr:
        ids = dict(corr["ids"])
        report["identifier_correction"] = {k: v for k, v in corr.items() if k != "ids"}

    mondo_term = await _mondo_term(ids["mondo_id"], session) if ids.get("mondo_id") else {}
    if ids.get("mondo_id") and not corr:
        # Every remaining MONDO ID must name the disease (label or synonym) — warn only.
        if not any(label_matches(n, mondo_term.get("label"), mondo_term.get("synonyms")) for n in names if n):
            report["mondo_label_note"] = mondo_term.get("label")
    orpha = await _verified_orpha(names, mondo_term, session) if mondo_term else None
    ids.pop("orpha_id", None)
    if orpha:
        ids["orpha_id"] = orpha
    if ids.get("efo_id") and not await _efo_ok(ids["efo_id"], names + [mondo_term.get("label") or ""], session):
        report["efo_dropped"] = ids.pop("efo_id")
    order = ["mondo_id", "efo_id", "omim_id", "orpha_id", "mesh_id", "umls_cui"]
    ids = {k: ids[k] for k in order if ids.get(k)}
    report["identifiers_after"] = ids

    di = DiseaseIdentifiers(name=name, **ids)
    old = data["alterations"]
    ot_old = [a for a in old if "Open Targets" in a.get("sources", [])]
    ct_old = [a for a in old if "ClinicalTrials.gov" in a.get("sources", [])]
    other = [a for a in old if a not in ot_old and a not in ct_old and not {"HPO", "Monarch", "Orphanet"} & set(a.get("sources", []))]
    if other:
        raise RuntimeError(f"{slug}: unexpected alteration sources {[a['sources'] for a in other][:3]}")

    # Open Targets
    ot_id = (ids.get("mondo_id") or ids.get("efo_id") or "").replace(":", "_") or None
    if corr:
        ot_new = await molecular._open_targets_genes(di, session) if ot_id else []
        report["ot"] = {"mode": "refetched_top100", "ot_id": ot_id, "rows": len(ot_new)}
    else:
        ens = [a["source_ids"].get("Ensembl", "") for a in ot_old]
        scores = await molecular.ot_association_scores(ot_id, ens, session) if (ot_id and ens) else {}
        ot_new = []
        for a in ot_old:
            alt = _to_alteration(a)
            sc = scores.get(a["source_ids"].get("Ensembl", ""))
            ot_new.append(
                alt.model_copy(
                    update={
                        "evidence_tier": EvidenceTier.N,
                        "association_score": round(sc, 4) if sc is not None else None,
                        "evidence_label": molecular.ot_score_label(sc),
                    }
                )
            )
        report["ot"] = {"mode": "scored_existing", "ot_id": ot_id, "rows": len(ot_new),
                        "scored": sum(1 for a in ot_new if a.association_score is not None)}

    # HPO: direct annotations only
    hpo_new = await clinical.get_hpo_phenotypes(None, session, mondo_id=ids.get("mondo_id")) if ids.get("mondo_id") else []
    old_hpo = {a["canonical_id"] for a in old if "HPO" in a.get("sources", [])}
    new_hpo = {a.canonical_id for a in hpo_new}
    report["hpo"] = {"before": len(old_hpo), "after": len(new_hpo), "kept": len(old_hpo & new_hpo),
                     "dropped_descendant_or_wrong_id": len(old_hpo - new_hpo), "added_direct": len(new_hpo - old_hpo)}

    # ClinicalTrials.gov: outcome measures
    ct_new = [
        _to_alteration(a).model_copy(
            update={"alteration_type": AlterationType.T, "evidence_tier": EvidenceTier.N,
                    "evidence_label": "Trial outcome measure"}
        )
        for a in ct_old
    ]
    report["ct"] = {"rows": len(ct_new)}

    merged = score.score_alterations(ot_new + hpo_new + ct_new)
    alts = sorted((_export_alteration(slug, a) for a in merged), key=_tier_sort_key_alt)
    counts: dict[str, int] = {}
    for a in alts:
        counts[a["type"]] = counts.get(a["type"], 0) + 1

    old_hero = data["page"]["hero"]
    n_ther = data["summary"]["therapeutic_counts"].get("merged", 0)
    new_hero = re.sub(r"\d+ alterations", f"{len(alts)} alterations", old_hero, count=1)
    data["identifiers"] = ids
    data["alterations"] = alts
    data["categories"] = dict(TYPE_LABELS)
    data["page"]["hero"] = new_hero
    data["page"]["dateModified"] = today
    s = data["summary"]
    s["alteration_count"] = len(alts)
    s["displayed_alterations"] = len(alts)
    s["alteration_counts_by_type"] = counts
    s["alteration_provenance"] = {
        "refreshed": today,
        "open_targets_release": ot_release,
        "hpo": "Monarch v3 association API, biolink:has_phenotype, direct=true (annotations of this MONDO class only)",
        "clinicaltrials": "outcome measures (type T) from the earlier ClinicalTrials.gov v2 query of completed studies",
        **({"identifier_correction": report["identifier_correction"]} if corr else {}),
    }
    report["rows_before"] = len(old)
    report["rows_after"] = len(alts)
    report["hero"] = (old_hero, new_hero, n_ther)
    report["_data"] = data
    return report


async def main_async(slugs: list[str] | None, dry_run: bool) -> int:
    today = date.today().isoformat()
    reports = []
    async with default_session() as session:
        ot_release = await molecular.ot_data_version(session)
        log.info("Open Targets release %s", ot_release)
        for path in sorted(DATA_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            slug = data.get("slug", path.stem)
            if slugs and slug not in slugs:
                continue
            if slug in EXCLUDED_SLUGS or not is_publishable(data):
                continue
            for attempt in range(4):
                try:
                    rep = await refresh_page(json.loads(json.dumps(data)), session, ot_release=ot_release, today=today)
                    break
                except Exception as e:  # network hiccups (OT / Monarch / OLS)
                    if attempt == 3:
                        raise
                    log.warning("%s: attempt %d failed (%s); retrying", slug, attempt + 1, e)
                    await asyncio.sleep(10 * (attempt + 1))
            data = rep.pop("_data")
            html_path = HTML_DIR / f"{slug}.html"
            if html_path.exists():
                live = html_path.read_text(encoding="utf-8")
                new_live, done = splice_html(live, build_html(data), rep["hero"][0], rep["hero"][1])
                rep["html_spliced"] = done
                if not dry_run:
                    html_path.write_text(new_live, encoding="utf-8")
            if not dry_run:
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            reports.append(rep)
            log.info("%s: %d -> %d rows %s", slug, rep["rows_before"], rep["rows_after"], rep.get("html_spliced"))
    manifest = {"refreshed": today, "open_targets_release": ot_release,
                "monarch_api": "https://api-v3.monarchinitiative.org/v3/api (direct=true)",
                "ols": "https://www.ebi.ac.uk/ols4/api", "pages": reports}
    if MANIFEST.exists() and slugs:
        # Partial re-run: merge into the existing manifest, keeping the original
        # "before" state of pages already refreshed.
        prev = {p["slug"]: p for p in json.loads(MANIFEST.read_text(encoding="utf-8")).get("pages", [])}
        for rep in reports:
            old = prev.get(rep["slug"])
            if old:
                rep["identifiers_before"] = old["identifiers_before"]
                rep["rows_before"] = old["rows_before"]
                if rep["hpo"]["before"] != old["hpo"]["before"]:
                    rep["hpo"] = {**rep["hpo"], "before": old["hpo"]["before"]}
            prev[rep["slug"]] = rep
        manifest["pages"] = [prev[k] for k in sorted(prev)]
    if not dry_run:
        MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    else:
        print(json.dumps(manifest, indent=1, ensure_ascii=False)[:4000])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slugs", help="comma-separated slugs (default: all published pages)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(main_async(args.slugs.split(",") if args.slugs else None, args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
