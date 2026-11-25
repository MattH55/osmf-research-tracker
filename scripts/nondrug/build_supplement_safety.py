#!/usr/bin/env python3
"""Feature 3: safety and interaction pages for supplements studied in non-drug trials.

For each supplement:
  * openFDA CAERS (FDA food/supplement adverse-event reports): reports where the SUSPECT product's
    brand name contains the supplement's name. openFDA's own count endpoint cannot tie the
    "suspect" role to the matching product, so records are fetched and filtered here. Shown with a
    "reports are not rates" callout. Generic names (probiotics, herbal products) get no number,
    because a brand-name match says nothing about their ingredients.
  * NIH text quoted verbatim with a link: the "Interactions with Medications" section of the NIH
    Office of Dietary Supplements health-professional fact sheet, or the safety section of the NCCIH
    page where ODS has no fact sheet. Nothing about interactions is written by OSMF.
  * registered trials from data/nondrug/nondrug_trials.json.

Network results are cached in data/nondrug/cache/safety/ (git-ignored); the compact result is written
to data/nondrug/supplement_safety.json (committed), so pages rebuild offline.

    python scripts/nondrug/build_supplement_safety.py --fetch   # refresh CAERS + NIH text
    python scripts/nondrug/build_supplement_safety.py           # render pages from the JSON
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ndsite import ROOT, SITE, esc, load_dataset, shell, trial_li, write  # noqa: E402

CACHE = ROOT / "data" / "nondrug" / "cache" / "safety"
OUT = ROOT / "data" / "nondrug" / "supplement_safety.json"
UA = {"User-Agent": "OSMF-research-tracker/1.0 (+https://research.opensourcemed.info)"}

# id, label, taxonomy class, CAERS brand terms (None = generic name, no count), NIH source (kind, url)
SUPPLEMENTS = [
    ("vitamin-d", "Vitamin D", "vitamin-d", ["VITAMIN D"], ("ods", "https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/")),
    ("omega-3", "Omega-3 fatty acids and fish oil", "omega-3", ["FISH OIL", "OMEGA-3", "OMEGA 3"], ("ods", "https://ods.od.nih.gov/factsheets/Omega3FattyAcids-HealthProfessional/")),
    ("magnesium", "Magnesium", "magnesium", ["MAGNESIUM"], ("ods", "https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/")),
    ("zinc", "Zinc", "zinc", ["ZINC"], ("ods", "https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/")),
    ("vitamin-c", "Vitamin C", "vitamin-c", ["VITAMIN C"], ("ods", "https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/")),
    ("vitamin-b12", "Vitamin B12", "b-vitamins", ["VITAMIN B12", "VITAMIN B-12", "B12"], ("ods", "https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/")),
    ("folate", "Folate and folic acid", "b-vitamins", ["FOLIC ACID", "FOLATE"], ("ods", "https://ods.od.nih.gov/factsheets/Folate-HealthProfessional/")),
    ("probiotics", "Probiotics", "probiotics", None, ("ods", "https://ods.od.nih.gov/factsheets/Probiotics-HealthProfessional/")),
    ("melatonin", "Melatonin", "melatonin", ["MELATONIN"], ("nccih", "https://www.nccih.nih.gov/health/melatonin-what-you-need-to-know")),
    ("coq10", "Coenzyme Q10", "coq10", ["COQ10", "COQ-10", "CO Q10", "COENZYME Q10", "CO-Q10"], ("nccih", "https://www.nccih.nih.gov/health/coenzyme-q10")),
    ("turmeric-curcumin", "Turmeric and curcumin", "curcumin-polyphenols", ["TURMERIC", "CURCUMIN"], ("nccih", "https://www.nccih.nih.gov/health/turmeric")),
    ("creatine", "Creatine", "creatine", ["CREATINE"], ("ods-section", "https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/", "Creatine")),
    ("nac", "N-acetylcysteine (NAC)", "nac", ["N-ACETYL CYSTEINE", "N-ACETYL-L-CYSTEINE", "N-ACETYLCYSTEINE"], None),
    ("nad-precursors", "Nicotinamide riboside and other NAD+ precursors", "nad-precursors", ["NICOTINAMIDE RIBOSIDE", "NIAGEN", "NMN"], None),
    ("herbal-tcm", "Herbal and traditional formulas", "herbal-tcm", None, ("nccih", "https://www.nccih.nih.gov/health/using-dietary-supplements-wisely")),
]


def fetch(url: str, cache_name: str, binary: bool = False) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / cache_name
    if f.exists():
        return f.read_text(encoding="utf-8")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                text = r.read().decode("utf-8", errors="replace")
            f.write_text(text, encoding="utf-8")
            time.sleep(0.4)
            return text
        except urllib.error.HTTPError as e:
            if e.code == 404:
                f.write_text('{"results": []}', encoding="utf-8")
                return '{"results": []}'
            time.sleep(4 * (attempt + 1))
        except Exception:
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}")


# Other names for the same ingredient: removed from a product name before looking for other ingredients.
OWN_NAMES = {"vitamin-d": ["CHOLECALCIFEROL", "ERGOCALCIFEROL", "D3", "D-3", "D2"], "omega-3": ["DHA", "EPA", "KRILL", "FISH", "OMEGA"],
             "vitamin-c": ["ASCORBIC ACID", "ASCORBATE"], "vitamin-b12": ["CYANOCOBALAMIN", "METHYLCOBALAMIN"],
             "folate": ["FOLIC", "METHYLFOLATE"], "turmeric-curcumin": ["TURMERIC", "CURCUMIN", "CURCUMINOIDS"],
             "nac": ["NAC", "N-A-C"], "nad-precursors": ["NAD", "NIAGEN", "NICOTINAMIDE"], "coq10": ["UBIQUINOL"]}
# Words in a product name that point to a second active ingredient, making it a combination product.
OTHER_INGREDIENT = re.compile(
    r"CALCIUM|CALTRATE|CITRACAL|OS-CAL|VITAMIN\s*[A-Z]|\bB-?\d+\b|\bK2\b|ZINC|MAGNESIUM|IRON|SELENIUM|POTASSIUM|MULTI|COMPLEX|ELECTROLYTE|"
    r"PRENATAL|AREDS|LUTEIN|GLUCOSAMINE|CHONDROITIN|ECHINACEA|ELDERBERRY|MELATONIN|ASCORBIC|FOLIC|BIOTIN|EMERGEN|FIBER|BENEFIBER|"
    r"COQ-?10|CO Q10|TURMERIC|CURCUMIN|CREATINE|PROTEIN|CAFFEINE|GREEN TEA|ASHWAGANDHA|COLLAGEN|GINKGO|GINSENG|PROBIOTIC|FISH OIL|OMEGA|"
    r"\+|&|\bPLUS\b|\bWITH\b")


def is_combination(brand: str, own: list[str]) -> bool:
    s = brand.upper()
    for t in sorted(own, key=len, reverse=True):
        s = s.replace(t.upper(), " ")
    return bool(OTHER_INGREDIENT.search(s))


def caers(terms: list[str], sid: str = "") -> dict:
    """Suspect-only CAERS reports whose suspect product brand contains one of the terms. Reports are split by whether
    a matched product is named for this ingredient alone or for a combination (judged from the product name)."""
    own = [t.strip() for t in terms] + OWN_NAMES.get(sid, [])
    rx = re.compile("|".join(re.escape(t.strip()) for t in terms), re.I)
    q = " OR ".join(f'products.name_brand:"{t.strip()}"' for t in terms)
    search = f"({q}) AND products.industry_code:54"
    seen, reactions, outcomes, years, single, products = set(), Counter(), Counter(), [], 0, Counter()
    skip = 0
    while skip <= 25000:
        url = "https://api.fda.gov/food/event.json?" + urllib.parse.urlencode({"search": search, "limit": 1000, "skip": skip})
        page = json.loads(fetch(url, f"caers-{re.sub('[^a-z0-9]', '', '-'.join(terms).lower())[:60]}-{skip}.json"))
        res = page.get("results") or []
        for r in res:
            hits = [p["name_brand"] for p in r.get("products") or [] if p.get("role") == "SUSPECT" and rx.search(p.get("name_brand") or "")]
            if hits:
                rid = r.get("report_number")
                if rid in seen:
                    continue
                seen.add(rid)
                products.update({re.sub(r"\s*\(.*$", "", h).strip().upper() for h in hits})
                if all(is_combination(h, own) for h in hits):
                    continue
                single += 1
                reactions.update({x.strip().capitalize() for x in r.get("reactions") or [] if x.strip()})
                outcomes.update({x.strip() for x in r.get("outcomes") or [] if x.strip()})
                if (r.get("date_created") or "")[:4].isdigit():
                    years.append(int(r["date_created"][:4]))
        if len(res) < 1000:
            break
        skip += 1000
    return {"reports": len(seen), "single": single, "top_products": products.most_common(6), "top_reactions": reactions.most_common(12), "outcomes": outcomes.most_common(8),
            "years": [min(years), max(years)] if years else None, "terms": terms}


def _headings(page: str) -> list[tuple[int, int, int, str]]:
    """(start, end, level, text) for every h2/h3, with embedded <style> rules removed from the text."""
    out = []
    for m in re.finditer(r"<h([23])[^>]*>(.*?)</h\1>", page, re.S | re.I):
        inner = re.sub(r"<style.*?</style>", "", m.group(2), flags=re.S | re.I)
        text = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", inner))).strip()
        text = re.sub(r"^\.[^{]*\{.*\}", "", text).strip()
        out.append((m.start(), m.end(), int(m.group(1)), text))
    return out


def nih_quote(kind: str, url: str, section: str | None = None) -> dict:
    """Verbatim text of one NIH section. kind: 'ods' (Interactions with Medications, else Safety Considerations),
    'nccih' (first safety heading), 'ods-section' (safety sentences inside a named sub-section)."""
    page = re.sub(r"<style.*?</style>", "", fetch(url, re.sub(r"[^a-z0-9]+", "-", url.lower())[-80:] + ".html"), flags=re.S | re.I)
    hs = _headings(page)
    target = None
    if kind == "ods":
        for want in ("interactions with medications", "safety considerations", "health risks"):
            hits = [h for h in hs if h[3].lower().startswith(want)]
            if hits:
                target = hits[-1]  # the last one: the first is usually the table of contents
                break
    elif kind == "nccih":
        target = next((h for h in hs if re.search(r"safe|side effect", h[3], re.I) and "for more" not in h[3].lower()), None)
    elif kind == "ods-section":
        hits = [h for h in hs if h[3].lower() == (section or "").lower()]
        target = hits[-1] if hits else None
    if not target:
        return {"kind": kind, "url": url, "heading": None, "paragraphs": [], "items": []}
    nxt = next((h for h in hs if h[0] > target[0] and h[2] <= target[2]), None)
    seg = page[target[1]: nxt[0] if nxt else target[1] + 8000]
    clean = lambda h: re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<sup.*?</sup>", "", h, flags=re.S)))).strip()
    paragraphs, items = [], []
    for m in re.finditer(r"<(p|h3|h4|li)[^>]*>(.*?)</\1>", seg, re.S | re.I):
        tag, text = m.group(1).lower(), clean(m.group(2))
        if not text:
            continue
        if tag in ("h3", "h4"):
            items.append(text)
            continue
        if kind == "ods-section" and not re.search(r"safe|adverse|side effect|interact|risk", text, re.I):
            continue
        if len(paragraphs) < 3 and len(" ".join(paragraphs)) < 900:
            paragraphs.append(text)
    return {"kind": kind, "url": url, "heading": target[3] if kind != "ods-section" else f"{section} (safety)",
            "paragraphs": paragraphs, "items": items[:12], "retrieved": date.today().isoformat()}


def do_fetch() -> None:
    out = {"built": date.today().isoformat(), "supplements": {}}
    for sid, label, cls, terms, src in SUPPLEMENTS:
        entry = {"label": label, "class": cls}
        if terms:
            entry["caers"] = caers(terms, sid)
        if src:
            entry["nih"] = nih_quote(*src)
        out["supplements"][sid] = entry
        print(f"  {sid}: CAERS {entry.get('caers', {}).get('reports', '–')} reports; NIH paragraphs {len((entry.get('nih') or {}).get('paragraphs', []))}, items {len((entry.get('nih') or {}).get('items', []))}")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


CALLOUT = ('<div class="nd-callout"><strong>Reports are not rates.</strong> CAERS counts voluntary reports to the FDA from consumers, '
           'clinicians and companies. A report means someone linked a health problem to a product, not that the product caused it. '
           'There is no denominator: how many people took the product is unknown, so these numbers cannot show how common a problem is, '
           'and they cannot be compared between products. Popular products attract more reports.</div>')


# Published-study safety summaries, copied (text unchanged) from the main site's verified library:
# data/nondrug/safety_library/<key>.json. Only entries that say something about the page's supplement are attached.
LIBRARY = ROOT / "data" / "nondrug" / "safety_library"
LIBRARY_KEYS = {"vitamin-d": "vitamin-d", "omega-3": "omega-3", "magnesium": "magnesium", "zinc": "zinc",
                "probiotics": "probiotics", "melatonin": "melatonin", "coq10": "coq10", "turmeric-curcumin": "curcumin",
                "creatine": "creatine", "nad-precursors": "nicotinamide-riboside",
                "vitamin-c": "vitamin-c", "nac": "n-acetylcysteine"}


def library_html(sid: str, label: str) -> str:
    key = LIBRARY_KEYS.get(sid)
    f = LIBRARY / f"{key}.json" if key else None
    if not f or not f.exists():
        return (f"<h2>Safety evidence from published studies</h2><p>No summary of published safety studies has been prepared for "
                f"{esc(in_sentence(label))} yet. The NIH text and FDA reports on this page are the safety sources for now.</p>")
    e = json.loads(f.read_text(encoding="utf-8"))
    refs = "".join(f'<li><a href="https://pubmed.ncbi.nlm.nih.gov/{esc(c["id"])}/" target="_blank" rel="noopener">{esc(c["label"])}</a>'
                   f'{(": " + esc(c["title"])) if c.get("title") else ""}</li>' for c in e["citations"])
    return (f"<h2>Safety evidence from published studies</h2><p>{esc(e['text'])}</p><ol class=\"nd-tlist\">{refs}</ol>"
            f"<p class=\"nd-method\">A summary of what the cited PubMed studies report, from studies in a range of people, not only one condition. "
            f"Each statement is checked against a quoted sentence from the study's abstract; copied {esc(e.get('copied_on', ''))}.</p>")


COMPOUND_INDEX = ROOT / "data" / "natural-products-review" / "compounds" / "index.json"
GRADE_CSS = ("<style>.np-g{display:inline-block;font-size:.78rem;font-weight:700;border-radius:999px;padding:.1rem .6rem}"
             ".g-A{background:#1b5e20;color:#fff}.g-B{background:#2e7d32;color:#fff}.g-C{background:#fff3cd;color:#5a4300}"
             ".g-D{background:#ede7f6;color:#3c2a6b}.g-Negative{background:#fde2e1;color:#8a1c14}.g-Insufficient{background:#eceff1;color:#37474f}</style>")


def reviews_html(sid: str, label: str, include_drafts: bool = False) -> str:
    """Evidence-graded reviews of this supplement, one row per condition. Published reviews only unless previewing."""
    key = LIBRARY_KEYS.get(sid)
    if not key or not COMPOUND_INDEX.exists():
        return ""
    doc = json.loads(COMPOUND_INDEX.read_text(encoding="utf-8"))
    rows = [r for r in doc["compounds"].get(key, {}).get("rows", []) if include_drafts or r["status"] == "published"]
    if not rows:
        return ""
    trs = ""
    for r in rows:
        how = "; ".join(x for x in ((("tested together with " + ", ".join(r["tested_with"])) if r["tested_with"] else "on its own"), r["route_note"]) if x)
        trs += (f'<tr><th scope="row"><a href="{esc(r["page"])}">{esc(r["condition"])}</a></th>'
                f'<td><span class="np-g g-{esc(r["grade"])}" title="{esc(doc["grade_key"][r["grade"]])}">{esc(r["grade"])}</span></td>'
                f'<td>{esc(how)}</td><td>{esc(r["summary"])}</td></tr>')
    key_txt = "; ".join(f"{g} = {t}" for g, t in doc["grade_key"].items())
    return (f"<h2>Evidence reviews by condition</h2>{GRADE_CSS}<p class=\"nd-method\">OSMF reviews of human studies of {esc(in_sentence(label))}, one condition per row. "
            "A grade applies to that condition only. When it was tested together with other ingredients, the grade belongs to the combination.</p>"
            '<div class="tbl-wrap"><table class="nd-tbl"><thead><tr><th scope="col">Condition</th><th scope="col">Review grade</th>'
            f'<th scope="col">How it was tested</th><th scope="col">What was found</th></tr></thead><tbody>{trs}</tbody></table></div>'
            f"<p class=\"nd-method\">Grades: {esc(key_txt)}.</p>")


def in_sentence(label: str) -> str:
    """'Vitamin D' -> 'vitamin D'; 'N-acetylcysteine (NAC)' stays as written."""
    return label[:1].lower() + label[1:] if len(label) > 1 and label[1].islower() else label


def render() -> None:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    d = load_dataset()
    trials = d["trials"]
    cards = []
    for sid, label, cls, terms, src in SUPPLEMENTS:
        e = doc["supplements"].get(sid)
        if not e:
            continue
        ncts = sorted((n for n, t in trials.items() if any(c == cls for c, _ in t["iv"])),
                      key=lambda n: (not trials[n]["r"], trials[n]["g"] != "completed"))
        cz = e.get("caers")
        if cz:
            yrs = f"{cz['years'][0]}–{cz['years'][1]}" if cz.get("years") else "–"
            react = "".join(f"<tr><th scope=\"row\">{esc(r)}</th><td class=\"n\">{n:,}</td></tr>" for r, n in cz["top_reactions"])
            outc = ", ".join(f"{esc(o)} ({n:,})" for o, n in cz["outcomes"])
            caers_html = f"""<h2>FDA adverse-event reports (CAERS)</h2>{CALLOUT}
<div class="nd-numbers"><div><b>{cz['reports']:,}</b><span>reports naming it in a suspect product</span></div><div><b>{cz['single']:,}</b><span>where the product is named for it alone</span></div><div><b>{yrs}</b><span>years covered, single-ingredient reports</span></div></div>
<p class="nd-method"><strong>Matching rule:</strong> reports in the dietary-supplement category where a product marked "suspect" has a brand name containing {', '.join('“' + esc(t.strip()) + '”' for t in cz['terms'])}. Products that contain it without naming it are missed. Reports where it was only taken alongside the suspect product are not counted.</p>
<p class="nd-method"><strong>Combination products:</strong> {cz['reports'] - cz['single']:,} of the reports involve only products whose name lists another ingredient, such as calcium or a multivitamin. Their reactions may come from that other ingredient or from the tablet itself, so the reactions below count only the {cz['single']:,} reports where a product is named for {esc(in_sentence(label))} alone. This split is made from product names and can misfile some products. Most-reported products: {esc('; '.join(f"{n.title()} ({c})" for n, c in cz['top_products']))}.</p>
<div class="tbl-wrap"><table class="nd-tbl"><caption class="sr-only">Most reported reactions, single-ingredient reports</caption><thead><tr><th scope="col">Most reported reactions (single-ingredient products)</th><th scope="col" class="n">Reports</th></tr></thead><tbody>{react}</tbody></table></div>
<p class="nd-method">Outcomes recorded in these reports (a report can have several): {outc or '–'}.</p>
<p class="nd-method">Source: <a href="https://open.fda.gov/apis/food/event/">openFDA food and supplement adverse events (CAERS)</a>, retrieved {esc(doc['built'])}.</p>"""
        else:
            caers_html = (f"<h2>FDA adverse-event reports (CAERS)</h2><p>No count is shown. “{esc(label)}” is a generic category, and CAERS "
                          "records brand names, so a name match would not show which reports involve these ingredients.</p>")
        nih = e.get("nih")
        if nih and nih.get("paragraphs"):
            src_name = "NIH National Center for Complementary and Integrative Health" if nih["kind"] == "nccih" else "NIH Office of Dietary Supplements, health-professional fact sheet"
            paras = "".join(f"<p>{esc(p)}</p>" for p in nih["paragraphs"])
            items = (f"<p><strong>Medicines covered in that section:</strong> {esc(', '.join(nih['items']))}.</p>"
                     if nih.get("items") and (nih.get("heading") or "").lower().startswith("interactions") else "")
            nih_html = (f"<h2>Interactions and safety, in NIH's words</h2><blockquote class=\"nd-quote\">{paras}{items}"
                        f"<cite>Quoted from the “{esc(nih.get('heading') or '')}” section: <a href=\"{esc(nih['url'])}\">{src_name}</a>, retrieved {esc(nih.get('retrieved') or doc['built'])}. Read the full page for the complete list and references.</cite></blockquote>")
        else:
            nih_html = ("<h2>Interactions and safety</h2><p>NIH does not publish a fact sheet for this supplement. "
                        "Ask a pharmacist or clinician to check it against any medicines you take.</p>")
        cnames = d["conditions"]
        tl = "".join(trial_li(n, trials[n], " · " + esc(", ".join(cnames[c]["name"] for c in trials[n]["c"][:2] if c in cnames))) for n in ncts[:20])
        trials_html = (f"<h2>Registered trials</h2><p>{len(ncts):,} trials in the <a href=\"/nondrug/{cls}.html\">non-drug evidence map</a> test this class of supplement. "
                       f"Trials with posted results are listed first; each shows the condition it was registered for. A trial testing it in one condition says nothing about another.</p><ul class=\"nd-tlist\">{tl}</ul>" if ncts else "")
        rv = reviews_html(sid, label)
        reviews_block = ("\n" + rv) if rv else ""
        if os.environ.get("NP_PREVIEW"):  # local check of draft reviews; _np_preview/ is gitignored
            pv = reviews_html(sid, label, include_drafts=True)
            if pv:
                (ROOT / "_np_preview").mkdir(exist_ok=True)
                (ROOT / "_np_preview" / f"supplement-safety-{sid}.html").write_text(
                    shell(path=f"supplement-safety/{sid}.html", title=f"PREVIEW {label}", description="preview", eyebrow="Preview",
                          h1=label, h1_span="draft reviews", lede="Local preview of draft reviews.", body=pv,
                          crumbs=[(label, f"{SITE}/supplement-safety/{sid}.html")], modified=doc["built"]), encoding="utf-8")
        body = f"""<p class="lede">What public sources say about the safety of {esc(in_sentence(label))}: FDA adverse-event reports, NIH guidance on interactions with medicines, and the registered trials that test it.</p>
<div class="disclaimer"><span>⚠️</span><div><strong>Research information, not medical advice.</strong> Supplements can interact with prescription medicines and affect conditions. Check with a pharmacist or your own clinician before starting or stopping one. Nothing here is a dose recommendation.</div></div>
{nih_html}
{library_html(sid, label)}{reviews_block}
{caers_html}
{trials_html}
<p class="nd-actions"><a href="/supplement-safety/index.html">All supplement safety pages</a> <a href="/nondrug/index.html">Non-drug evidence map</a></p>"""
        path = f"supplement-safety/{sid}.html"
        desc = f"{label}: FDA adverse-event reports (reports are not rates), NIH guidance on interactions with medicines, and registered clinical trials. Research information, not medical advice."
        write(path, shell(path=path, title=f"{label}: safety, interactions and trials"[:70], description=desc,
                          eyebrow="Supplement safety · public sources", h1=label, h1_span="safety",
                          lede="FDA adverse-event reports, NIH guidance on interactions, and registered trials.", body=body,
                          crumbs=[("Supplement safety", f"{SITE}/supplement-safety/index.html"), (label, f"{SITE}/{path}")], modified=doc["built"]))
        n_rep = f"{cz['single']:,} single-ingredient CAERS reports" if cz else "no CAERS count (generic name)"
        cards.append(f'<a class="nd-card" href="/supplement-safety/{sid}.html"><strong>{esc(label)}</strong><span>{n_rep} · {len(ncts):,} trials'
                     f'{" · NIH interaction text" if nih and nih.get("paragraphs") else ""}</span></a>')
    body = f"""<p class="lede">Safety information from public sources for supplements that appear in registered non-drug trials. Each page quotes NIH's own text on interactions with medicines and shows FDA adverse-event reports with their limits stated.</p>
<div class="disclaimer"><span>⚠️</span><div><strong>Research information, not medical advice.</strong> “Natural” does not mean safe for you. Check supplements with a pharmacist or clinician, especially alongside prescription medicines.</div></div>
{CALLOUT}
<div class="nd-cards">{''.join(cards)}</div>
<div class="box"><h2>Sources and limits</h2><ul class="nd-method">
<li><strong>NIH text</strong> is quoted verbatim from the Office of Dietary Supplements health-professional fact sheets or, where none exists, the National Center for Complementary and Integrative Health. OSMF does not write its own interaction guidance: NIH text is quoted verbatim, and each page's &quot;Safety evidence from published studies&quot; section restates what cited PubMed studies report, with every statement checked against a quoted sentence from the abstract.</li>
<li><strong>CAERS</strong> is the FDA's database of adverse-event reports for foods, supplements and cosmetics. Only reports naming the product as the suspect are counted, and reactions are shown only for products named for that supplement alone, because combination products such as calcium with vitamin D dominate some counts. Generic categories get no count.</li>
<li><strong>Not covered:</strong> curated interaction databases (most are not openly licensed), device adverse events, and NPxP drug-modifier interaction data, which is published separately on <a href="https://npxp.opensourcemed.info/">npxp.opensourcemed.info</a> and covers cancer cell lines.</li>
</ul></div>"""
    write("supplement-safety/index.html", shell(path="supplement-safety/index.html", title="Supplement safety: interactions, adverse-event reports and trials",
                                                description="Public-source safety information for supplements in registered trials: NIH guidance on interactions with medicines, FDA adverse-event reports and trials.",
                                                eyebrow="Research Tracker · supplement safety", h1="Supplement", h1_span="safety",
                                                lede=f"{len(cards)} supplements, built {esc(doc['built'])}.", body=body,
                                                crumbs=[("Supplement safety", f"{SITE}/supplement-safety/index.html")], modified=doc["built"]))
    print(f"supplement-safety: {len(cards)} pages + index")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    if a.fetch or not OUT.exists():
        do_fetch()
    render()
