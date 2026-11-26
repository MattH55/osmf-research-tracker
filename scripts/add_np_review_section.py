#!/usr/bin/env python3
"""Add the evidence-graded natural-products review to RepurpOS condition pages.

    python scripts/add_np_review_section.py               # update disease-intelligence/*.html in place
    python scripts/add_np_review_section.py --preview     # also render DRAFT reviews, into _np_preview/ only

Data: data/natural-products-review/<slug>.json, exported read-only from opensourcemed.info by
tools/export_np_to_tracker.py (never edit by hand). A review appears on its RepurpOS page only when its
"status" is "published"; a draft removes any earlier block. The block sits between
<!-- OSMF_NP_REVIEW_START --> and <!-- OSMF_NP_REVIEW_END -->, just above the pipeline's Natural Products
section, so re-running is idempotent and the pipeline's own tiers are never changed.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEWS = ROOT / "data" / "natural-products-review"
PAGES = ROOT / "disease-intelligence"
PIPELINE = ROOT / "data" / "disease-intelligence"
PREVIEW = ROOT / "_np_preview"
DRAFTS = PREVIEW / "data"  # gitignored: every review, drafts included (written by the main-site export)
START, END = "<!-- OSMF_NP_REVIEW_START -->", "<!-- OSMF_NP_REVIEW_END -->"
BLOCK_RE = re.compile(r"[ \t]*" + re.escape(START) + r".*?" + re.escape(END) + r"\r?\n?", re.S)
ANCHOR = '<section id="natural-products">'

# review slug -> (RepurpOS page slug, scope note when the page is broader than the review)
PAGE_FOR = {
    "fibromyalgia": ("fibromyalgia", ""),
    "migraine": ("migraine-disorder", ""),
    "me-cfs": ("myalgic-encephalomyelitis-chronic-fatigue-syndrome", ""),
    "alopecia-areata": ("alopecia-areata", ""),
    "alzheimers-disease": ("alzheimers-disease-and-other-dementias",
                           "This review covers Alzheimer's disease and dementia prevention; this page covers Alzheimer's disease and other dementias."),
    "major-depressive-disorder": ("major-depressive-disorder", ""),
    "osteoarthritis": ("osteoarthritis", ""),
    "rheumatoid-arthritis": ("rheumatoid-arthritis", ""),
    "irritable-bowel-syndrome": ("irritable-bowel-syndrome", ""),
    "insomnia": ("insomnia", ""),
    "obesity": ("obesity", ""),
    "schizophrenia": ("schizophrenia", ""),
    "asthma": ("asthma", ""),
    "type-1-diabetes": ("type-1-diabetes", ""),
    "multiple-sclerosis": ("multiple-sclerosis", ""),
    "anxiety": ("anxiety", ""),
    "heart-failure": ("heart-failure", ""),
    "chronic-kidney-disease": ("chronic-kidney-disease", ""),
    "acne": ("acne", ""),
    "peripheral-arterial-disease": ("peripheral-arterial-disease", ""),
    "bipolar-disorder": ("bipolar-disorder", ""),
    "chronic-obstructive-pulmonary-disease": ("chronic-obstructive-pulmonary-disease", ""),
    "psoriatic-arthritis": ("psoriatic-arthritis", ""),
    "epilepsy": ("epilepsy", ""),
    "diabetic-neuropathy": ("diabetic-neuropathy", ""),
    "cystic-fibrosis": ("cystic-fibrosis", ""),
    "parkinson-disease": ("parkinson-disease", ""),
    "osteoporosis": ("osteoporosis", ""),
    "sarcopenia": ("sarcopenia", ""),
    "tinnitus": ("tinnitus", ""),
    "ankylosing-spondylitis": ("ankylosing-spondylitis", ""),
    "chronic-venous-insufficiency": ("chronic-venous-insufficiency", ""),
    "hepatitis-c": ("hepatitis-c", ""),
    "inflammatory-bowel-disease": ("inflammatory-bowel-disease", ""),
    "benign-prostatic-hyperplasia": ("benign-prostatic-hyperplasia", ""),
    "endometriosis": ("endometriosis", ""),
    "vitiligo": ("vitiligo", ""),
    "glaucoma": ("glaucoma", ""),
    "gout": ("gout", ""),
    "hypothyroidism": ("hypothyroidism", ""),
    "carpal-tunnel-syndrome": ("carpal-tunnel-syndrome", ""),
    "type-2-diabetes": ("type-2-diabetes", ""),
    "age-related-macular-degeneration": ("age-related-macular-degeneration", ""),
    "polycystic-ovary-syndrome": ("polycystic-ovary-syndrome", ""),
    "psoriasis": ("psoriasis-vulgaris", ""),
    "ischemic-stroke": ("ischemic-stroke", ""),
    "hypertension": ("essential-hypertension", ""),
    "adhd": ("attention-deficit-hyperactivity-disorder", ""),
    # long-covid: the RepurpOS long-covid page is a redirect stub, so there is no page to add the review to.
}
esc = html.escape

CSS = """<style>
.np-rev .np-rev-sub{color:#4a5170;font-size:.92rem;line-height:1.6;max-width:860px}
.np-rev .np-rev-lead{background:#f6f7fb;border-left:4px solid #e65100;border-radius:10px;padding:.9rem 1.1rem;margin:1rem 0 1.2rem;max-width:860px;line-height:1.65}
.np-rev .np-rev-item{border:1px solid rgba(14,20,68,.12);border-radius:12px;padding:.9rem 1.1rem;margin:0 0 .8rem;background:#fff}
.np-rev .np-rev-item h3{font-size:1.02rem;margin:0 0 .3rem;display:flex;flex-wrap:wrap;gap:.5rem;align-items:center}
.np-rev .np-rev-item p{margin:.35rem 0;line-height:1.6;font-size:.93rem;color:#2b3050}
.np-rev .np-rev-meta{font-size:.82rem;color:#4a5170}
.np-rev .np-g{display:inline-block;font-size:.78rem;font-weight:700;border-radius:999px;padding:.1rem .6rem}
.np-rev .g-A{background:#1b5e20;color:#fff}.np-rev .g-B{background:#2e7d32;color:#fff}.np-rev .g-C{background:#fff3cd;color:#5a4300}
.np-rev .g-D{background:#ede7f6;color:#3c2a6b}.np-rev .g-Negative{background:#fde2e1;color:#8a1c14}.np-rev .g-Insufficient{background:#eceff1;color:#37474f}
.np-rev ol{font-size:.85rem;padding-left:1.3rem;margin:.4rem 0 0}
.np-rev details summary{cursor:pointer;font-size:.85rem;color:#1a1f3a;font-weight:600}
.np-rev .np-rev-key{font-size:.85rem;border-collapse:collapse;margin:.6rem 0}
.np-rev .np-rev-key td,.np-rev .np-rev-key th{padding:.3rem .6rem;border-bottom:1px solid rgba(14,20,68,.1);text-align:left;vertical-align:top}
.np-rev .np-rev-disc{font-size:.88rem;background:#f6f7fb;border-radius:10px;padding:.7rem 1rem}
</style>"""


def in_sentence(s: str) -> str:
    """'Migraine' -> 'migraine'; 'ME/CFS' and "Alzheimer's disease" stay as written."""
    return s if s.startswith("Alzheimer") or len(s) < 2 or not s[1].islower() else s[0].lower() + s[1:]


def human_date(iso: str) -> str:
    from datetime import date
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\(.*?\)", "", s.lower())).strip()


def pipeline_tiers(page_slug: str) -> dict[str, tuple[str, str]]:
    f = PIPELINE / f"{page_slug}.json"
    if not f.exists():
        return {}
    out = {}
    for np_ in json.loads(f.read_text(encoding="utf-8")).get("natural_products") or []:
        for n in [np_.get("name") or ""] + (np_.get("common_names") or []):
            if n:
                out.setdefault(norm(n), (np_.get("evidence_tier") or "", np_.get("evidence_tier_label") or "", np_.get("name") or n))
    return out


def compound_index() -> dict:
    f = DRAFTS / "compounds" / "index.json"  # ingredient names only are used here
    if not f.exists():
        f = REVIEWS / "compounds" / "index.json"
    return json.loads(f.read_text(encoding="utf-8"))["compounds"] if f.exists() else {}


def match_tier(p: dict, tiers: dict) -> tuple[str, str, str] | None:
    """(tier, label, pipeline row name) for a single-ingredient product. Combinations are not matched: the pipeline
    row is for one ingredient. The product's own name is tried before the ingredient's other pipeline names."""
    comps = p.get("compounds") or []
    if len(comps) > 1 or p.get("no_pipeline_match"):  # flag set by hand when the family key would match a different substance
        return None
    names = [p["name"]] + p.get("aliases", [])
    for k in comps:
        names += compound_index().get(k, {}).get("pipeline_names", [])
    for n in names:
        k = norm(n)
        if k in tiers:
            return tiers[k]
    return None


def how_tested(p: dict) -> str:
    comps = p.get("compounds") or []
    bits = []
    if len(comps) > 1:
        names = [compound_index().get(k, {}).get("name", k) for k in comps]
        bits.append("a combination of " + ", ".join(names) + ", so the grade is for the combination")
    if p.get("route_note"):
        bits.append(p["route_note"])
    return (" · Tested as: " + esc("; ".join(bits))) if bits else ""


def block(rev: dict, page_slug: str, scope: str) -> str:
    tiers = pipeline_tiers(page_slug)
    items = []
    for p in rev["products"]:
        cites = "".join(f'<li><a href="{esc(c["url"])}" target="_blank" rel="noopener">{esc(c["label"])}</a>'
                        f'{" · general safety source" if c.get("note") else ""}</li>' for c in p["citations"])
        general = "".join(f" <strong>General safety ({esc(g['name'])}):</strong> {esc(g['short'])}" for g in p["general_safety"])
        tier = match_tier(p, tiers)
        same = tier and norm(tier[2]) in {norm(n) for n in [p["name"]] + p.get("aliases", [])}
        intro = ("Also in" if same else f"A related entry, “{esc(tier[2])}”, is in") if tier else ""
        xref = (f'<p class="np-rev-meta">{intro} the <a href="#natural-products">Natural Products table</a> below, with pipeline evidence tier '
                f'{esc(tier[0])}{" (" + esc(tier[1]) + ")" if tier[1] else ""}. That tier ranks registry and literature signals and is a different scale from this review grade.</p>') if tier and tier[0] else ""
        design = p["best_design"] if p["best_design"] != "none" else (
            "No trials of benefit found; sources below are about safety" if p["citations"] else "No human studies found")
        rct = f" · {p['n_rcts']} randomized trial{'s' if p['n_rcts'] != 1 else ''} cited" if p["n_rcts"] else ""
        items.append(f'''<article class="np-rev-item"><h3>{esc(p["name"])} <span class="np-g g-{esc(p["grade"])}" title="Review grade: {esc(rev["grade_key"][p["grade"]])}">Review grade {esc(p["grade"])}</span></h3>
<p class="np-rev-meta">Best evidence: {esc(design)}{rct}{how_tested(p)}</p>
<p>{esc(p["summary"])}</p>
<p><strong>Safety and interactions:</strong> {esc(p["safety_interactions"])}{general}</p>
{xref}{f'<details><summary>Sources ({len(p["citations"])})</summary><ol>{cites}</ol></details>' if cites else ''}</article>''')
    key = "".join(f'<tr><th scope="row"><span class="np-g g-{esc(g)}">{esc(g)}</span></th><td>{esc(t)}</td></tr>' for g, t in rev["grade_key"].items())
    return f'''{START}
    <section id="natural-products-review" class="np-rev">
      {CSS}
      <h2 class="section-title">Natural Products: Evidence-Graded Review</h2>
      <p class="np-rev-sub">An OSMF review of human studies of natural products in {esc(in_sentence(rev["condition"]))}. Each product is graded from the abstracts of the cited studies, with its safety and interactions. {esc(scope)} These review grades are a separate scale from the evidence tiers in the Natural Products table below. Last reviewed {esc(human_date(rev["last_reviewed"]))} by {esc(rev["reviewed_by"])}. <a href="{esc(rev["page"])}">Full review with FAQ</a>.</p>
      <div class="np-rev-lead">{esc(rev["lead"])}</div>
      {"".join(items)}
      <details><summary>How the review grades work</summary><table class="np-rev-key"><tbody>{key}</tbody></table></details>
      <p class="np-rev-disc"><strong>{esc(rev["disclaimer"])}</strong></p>
    </section>
{END}
'''


def apply(page_html: str, rev: dict | None, page_slug: str, scope: str) -> str:
    out = BLOCK_RE.sub("", page_html)
    if rev is None:
        return out
    i = out.find(ANCHOR)
    if i < 0:
        raise SystemExit(f"{page_slug}: no Natural Products section to anchor on")
    line_start = out.rfind("\n", 0, i) + 1
    return out[:line_start] + block(rev, page_slug, scope) + out[line_start:]


def main() -> int:
    preview = "--preview" in sys.argv
    changed, shown = [], []
    for rslug, (page_slug, scope) in PAGE_FOR.items():
        f = REVIEWS / f"{rslug}.json"  # present only when the review is published
        d = DRAFTS / f"{rslug}.json"
        page = PAGES / f"{page_slug}.html"
        if not page.exists():
            print(f"skip {rslug}: no RepurpOS page")
            continue
        pub = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        rev = pub or (json.loads(d.read_text(encoding="utf-8")) if d.exists() else {"status": "draft"})
        with open(page, encoding="utf-8", newline="") as fh:
            cur = fh.read()
        live = apply(cur, pub if pub and pub["status"] == "published" else None, page_slug, scope)
        if live != cur:
            with open(page, "w", encoding="utf-8", newline="") as fh:
                fh.write(live)
            changed.append(page_slug)
        if rev["status"] == "published":
            shown.append(page_slug)
        if preview and "products" in rev:
            PREVIEW.mkdir(exist_ok=True)
            with open(PREVIEW / f"{page_slug}.html", "w", encoding="utf-8", newline="") as fh:
                fh.write(apply(cur, rev, page_slug, scope))
    print(f"natural-products review: shown on {len(shown)} RepurpOS pages {shown}; pages changed: {changed or 'none'}"
          + (f"; draft previews in {PREVIEW.relative_to(ROOT)}/" if preview else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
