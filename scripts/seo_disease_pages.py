#!/usr/bin/env python3
"""Search-intent metadata for chronic-disease-interventions/*.html.

Rewrites <title>, meta description, Open Graph and Twitter tags with the
phrasing people actually search for ("<disease> drug targets", "repurposed
drugs for <disease>", "<disease> clinical trials") and with concrete counts
pulled from the page itself, so every description is unique.  Also:

  * replaces the generic hero sentence with a lede that states the counts
  * turns the three <div class="section-title"> labels into real <h2>s
  * demotes agent-name <h3>s (inline-styled, in the disease-level search
    section) to <p> so trial-arm names stop acting as page headings
  * points the duplicate disease pages at their canonical twin

Safe to re-run after `generate_disease_pages.py`; idempotent.

    python scripts/seo_disease_pages.py            # apply
    python scripts/seo_disease_pages.py --dry-run  # report only
    python scripts/seo_disease_pages.py --only migraine.html
"""
from __future__ import annotations

import argparse
import html
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "chronic-disease-interventions"
ORIGIN = "https://research.opensourcemed.info"

MAX_TITLE = 65
MAX_DESC = 155

# Long H1s need a short search-friendly name for the <title>.
SHORT_NAMES = {
    "Alzheimer's Disease and Other Dementias": "Alzheimer's Disease & Dementia",
    "Inflammatory Bowel Disease (Crohn's/UC)": "IBD (Crohn's & Ulcerative Colitis)",
    "Inflammatory Bowel Disease (Crohn's / UC)": "IBD (Crohn's & Ulcerative Colitis)",
    "NAFLD / MASH (Metabolic-Associated Steatohepatitis)": "NAFLD / MASH Fatty Liver",
    "GERD (Gastroesophageal Reflux Disease)": "GERD (Acid Reflux)",
    "Polycythaemia Vera / Myeloproliferative Neoplasms": "Polycythaemia Vera",
    "Age-Related Hearing Loss (Presbycusis)": "Age-Related Hearing Loss",
    "Age-Related Macular Degeneration (AMD)": "Macular Degeneration (AMD)",
    "Alpha-1 Antitrypsin Deficiency (AATD)": "Alpha-1 Antitrypsin Deficiency",
    "Amyotrophic Lateral Sclerosis (ALS)": "ALS (Motor Neurone Disease)",
    "Ankylosing Spondylitis / Axial Spondyloarthropathy": "Ankylosing Spondylitis",
    "Atopic Dermatitis (Eczema)": "Atopic Dermatitis (Eczema)",
    "Immune Thrombocytopaenia (ITP)": "Immune Thrombocytopenia (ITP)",
    "Chronic Lymphocytic Leukaemia (CLL)": "Chronic Lymphocytic Leukaemia",
    "Benign Prostatic Hyperplasia (BPH)": "Benign Prostatic Hyperplasia",
    "Coeliac Disease (Refractory / RCD)": "Refractory Coeliac Disease",
    "Chronic Fatigue Syndrome / ME/CFS": "ME/CFS",
    "ME/CFS (Myalgic Encephalomyelitis / Chronic Fatigue Syndrome)": "ME/CFS",
    "Chronic Urticaria (CSU)": "Chronic Urticaria",
    "Chronic Venous Insufficiency / Venous Leg Ulcers": "Chronic Venous Insufficiency",
    "Inflammatory Myopathies (Dermatomyositis / PM / IBM)": "Inflammatory Myopathies",
    "Peripheral Neuropathy (Diabetic Peripheral Neuropathy)": "Diabetic Neuropathy",
    "Haemophilia A / B": "Haemophilia",
    "Hyperlipidemia / Dyslipidemia": "High Cholesterol (Dyslipidemia)",
    "Insomnia / Sleep Disorders": "Insomnia",
    "Interstitial Cystitis / Bladder Pain Syndrome (IC/BPS)": "Interstitial Cystitis",
    "Interstitial Lung Disease / Pulmonary Fibrosis": "Pulmonary Fibrosis",
    "Irritable Bowel Syndrome (IBS)": "Irritable Bowel Syndrome",
    "Ischemic Heart Disease / Coronary Artery Disease": "Coronary Artery Disease",
    "Stroke (Ischaemic / Cerebrovascular Disease)": "Ischaemic Stroke",
    "Stroke (Secondary Prevention)": "Stroke Secondary Prevention",
    "Long COVID / Post-Acute Sequelae (PACVS)": "Long COVID (PASC)",
    "Long COVID / Post-Acute COVID Sequelae (PACVS)": "Long COVID (PASC)",
    "Lyme Disease / Post-Treatment Lyme Disease Syndrome (PTLDS)": "Lyme Disease & PTLDS",
    "Myasthenia Gravis (MG)": "Myasthenia Gravis",
    "Myelodysplastic Syndromes (MDS)": "Myelodysplastic Syndromes",
    "Kidney Stones (Nephrolithiasis)": "Kidney Stones",
    "Non-Hodgkin Lymphoma (NHL)": "Non-Hodgkin Lymphoma",
    "Obesity (Severe / Morbid)": "Severe Obesity",
    "Obstructive Sleep Apnoea (OSA)": "Sleep Apnoea",
    "Peripheral Artery Disease (PAD)": "Peripheral Artery Disease",
    "Polycystic Kidney Disease (ADPKD)": "Polycystic Kidney Disease",
    "PCOS (Polycystic Ovary Syndrome)": "PCOS",
    "Pulmonary Arterial Hypertension (PAH)": "Pulmonary Arterial Hypertension",
    "Restless Legs Syndrome (RLS)": "Restless Legs Syndrome",
    "Primary Sclerosing Cholangitis (PSC)": "Primary Sclerosing Cholangitis",
    "Systemic Lupus Erythematosus (SLE)": "Lupus (SLE)",
    "Tension Headache / Chronic Daily Headache": "Chronic Daily Headache",
    "Thyroid Cancer (Well-Differentiated)": "Thyroid Cancer",
}

# The Long COVID pages mislabel PASC as PACVS (post-acute COVID vaccination
# syndrome).  Correct the H1 wording while we are here.
H1_FIXES = {
    "Long COVID / Post-Acute Sequelae (PACVS)": "Long COVID / Post-Acute Sequelae of COVID-19 (PASC)",
    "Long COVID / Post-Acute COVID Sequelae (PACVS)": "Long COVID / Post-Acute Sequelae of COVID-19 (PASC)",
}

# duplicate page -> page that already earns impressions (canonical twin)
CANONICAL_TWINS = {
    "alcohol-abuse.html": "alcohol-use-disorder.html",
    "anxiety.html": "anxiety-disorders.html",
    "chronic-obstructive-pulmonary-disease.html": "copd.html",
    "gastroesophageal-reflux-disease.html": "gerd-gastroesophageal-reflux-disease.html",
    "essential-hypertension.html": "hypertension.html",
    "inflammatory-bowel-disease.html": "inflammatory-bowel-disease-crohn-s-uc.html",
    "metabolic-dysfunction-associated-steatohepatitis.html": "nafld-mash-metabolic-associated-steatohepatitis.html",
    "parkinson-disease.html": "parkinson-s-disease.html",
    "systemic-lupus-erythematosus.html": "systemic-lupus-erythematosus-sle.html",
    # legacy orphan (not in db100, never regenerated) -> the live PACVS page
    "long-covid-post-acute-sequelae-pacvs.html": "post-acute-covidvaccination-syndrome.html",
}


NOTE_START, NOTE_END = "<!-- OSMF_NOTE_LINK_START -->", "<!-- OSMF_NOTE_LINK_END -->"
MAIN_NOTES = ROOT.parent / "research-notes"
MAIN_SITE = "https://opensourcemed.info"


def load_note_map() -> dict[str, tuple[str, str]] | None:
    """tracker slug -> (note URL, note question) from the main-site checkout."""
    if not MAIN_NOTES.is_dir():
        return None
    out: dict[str, tuple[str, str]] = {}
    for note in sorted(MAIN_NOTES.glob("*.html")):
        markup = note.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'href="https://research\.opensourcemed\.info/chronic-disease-interventions/([^"/]+)\.html"', markup)
        t = re.search(r"<title>(.*?)</title>", markup, re.S)
        if m and t:
            question = html.unescape(t.group(1)).split(" | ")[0].strip()
            out.setdefault(m.group(1), (f"{MAIN_SITE}/research-notes/{note.name}", question))
    return out


NOTE_MAP = load_note_map()


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def h1_of(markup: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", markup, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def counts(markup: str) -> tuple[int, int, int]:
    genes = len(re.findall(r'<div class="gene-card" id="gene-', markup))
    trials = len(re.findall(r'<div class="trial-card">', markup))
    m = re.search(r"(\d+) agents shown \(approved or with trial evidence\)", markup)
    agents = int(m.group(1)) if m else 0
    return genes, agents, trials


def build_title(name: str, agents: int = 0, trials: int = 0) -> str:
    """Patient-intent first ("<disease> drugs", "new drugs for <disease>"),
    with the candidate count up front because numbers lift CTR.  Search
    Console (Oct 2026) showed these pages at positions 4-9 with zero clicks
    under the researcher-jargon "Drug Targets" titles."""
    short = SHORT_NAMES.get(name, name)
    patterns = []
    if agents:
        patterns += [
            f"{short}: {agents} Approved & Investigational Drugs",
            f"{short}: {agents} Approved & Trial Drugs",
            f"{short}: {agents} Drug Candidates",
        ]
    if trials:
        patterns += [f"{short} Drugs & {trials} Clinical Trials"]
    for pattern in patterns + [
        f"{short}: Drug Targets, Repurposed Drugs & Trials | OSMF",
        f"{short}: Drug Targets, Repurposed Drugs & Trials",
        f"{short}: Drug Targets & Repurposed Drugs",
        f"{short} Drug Targets & Trials",
    ]:
        if len(pattern) <= MAX_TITLE:
            return pattern
    return f"{short} Drug Targets"[:MAX_TITLE]


def build_desc(name: str, genes: int, agents: int, trials: int) -> str:
    """Question-led snippet that mirrors the searcher's question, then the
    concrete counts.  Longest variant that fits MAX_DESC wins."""
    stamp = f"{date.today():%B %Y}"
    short = SHORT_NAMES.get(name, name)
    facts = []
    if agents:
        facts.append(f"{agents} candidates ranked by evidence")
    if trials:
        facts.append(f"{trials} clinical trials")
    if genes:
        facts.append(f"{genes} drug targets")
    if facts:
        for who in (name, short):
            for n_facts in range(len(facts), 0, -1):
                f = facts[:n_facts]
                joined = ", ".join(f[:-1]) + (" and " if len(f) > 1 else "") + f[-1]
                for tail in (f", each with sources. Updated {stamp}.", ", each with sources.", "."):
                    desc = f"Which drugs are approved or being tested for {who}? {joined[0].upper() + joined[1:]}{tail}"
                    if len(desc) <= MAX_DESC:
                        return desc
    return build_desc_legacy(name, genes, agents, trials)


def build_desc_legacy(name: str, genes: int, agents: int, trials: int) -> str:
    parts = []
    if genes:
        parts.append(f"{genes} druggable gene targets")
    if agents:
        parts.append(f"{agents} approved or trial-stage drug candidates")
    if trials:
        parts.append(f"{trials} clinical trials")
    lead = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] if parts else "Gene targets, drug candidates and trials"
    stamp = f"{date.today():%B %Y}"
    short = SHORT_NAMES.get(name, name)
    # longest variant that fits; the disease name shrinks before the wording does
    for who in (name, short):
        for tail in (
            f"ranked by evidence from DGIdb, Open Targets, ChEMBL and PubMed. Free, open-source, updated {stamp}.",
            f"ranked by evidence tier. Open-source, updated {stamp}.",
            f"ranked by evidence tier. Updated {stamp}.",
            "ranked by evidence tier, with sources.",
            "ranked by evidence.",
        ):
            desc = f"{lead} for {who}, {tail}"
            if len(desc) <= MAX_DESC:
                return desc
    return f"{lead} for {short}."[:MAX_DESC]


def build_lede(name: str, genes: int, agents: int, trials: int) -> str:
    bits = []
    if genes:
        bits.append(f"<strong>{genes} druggable gene targets</strong>")
    if agents:
        bits.append(f"<strong>{agents} approved or trial-tested drug candidates</strong>")
    if trials:
        bits.append(f"<strong>{trials} recent clinical trials</strong>")
    if not bits:
        return "Pharmacologically actionable gene targets, therapeutic agents ranked by evidence tier, and active clinical trials."
    joined = ", ".join(bits[:-1]) + (" and " if len(bits) > 1 else "") + bits[-1]
    repurposed = " Candidates include existing drugs that could be repurposed." if agents else ""
    return (f"This page lists {joined} for {esc(name)}, with each agent ranked by the strength of its evidence "
            f"(clinical, mechanistic or correlative).{repurposed} Sources are linked so you can check every claim.")


def set_tag(markup: str, pattern: str, replacement: str) -> str:
    return re.sub(pattern, replacement, markup, count=1, flags=re.I | re.S)


def process(page: Path, dry: bool) -> list[str]:
    markup = page.read_text(encoding="utf-8")
    original = markup
    notes: list[str] = []

    name = h1_of(markup)
    if name in H1_FIXES:
        markup = set_tag(markup, r"<h1([^>]*)>.*?</h1>", rf"<h1\1>{esc(H1_FIXES[name])}</h1>")
        name = H1_FIXES[name]
        notes.append("h1 relabelled")

    genes, agents, trials = counts(markup)
    empty = not (genes or agents or trials)
    if empty:
        # Nothing behind the promise yet: keep it honest and out of the index
        # until the pipeline populates the page (re-running lifts the noindex).
        short = SHORT_NAMES.get(name, name)
        title = f"{short}: Drug Targets & Repurposing (in progress) | OSMF"
        if len(title) > MAX_TITLE:
            title = f"{short}: Drug Targets (in progress) | OSMF"
        desc = (f"Druggable gene targets, repurposed drug candidates and clinical trials for {name} "
                f"are being compiled by the OSMF biomarker pipeline. Check back soon.")
        if len(desc) > MAX_DESC:
            desc = f"Gene targets, repurposed drugs and trials for {short} are being compiled. Check back soon."
    else:
        title = build_title(name, agents, trials)
        desc = build_desc(name, genes, agents, trials)
    # one robots tag only: flip the generator's own tag rather than adding a
    # second, conflicting one
    robots_pat = r'<meta name="robots" content="[^"]*"[^>]*>'
    want = "noindex,follow" if empty else "index, follow, max-image-preview:large"
    current = re.findall(robots_pat, markup, flags=re.I)
    if current:
        first = current[0]
        if want not in first or len(current) > 1:
            markup = re.sub(robots_pat, "", markup, flags=re.I)
            markup = markup.replace("</head>", f'<meta name="robots" content="{want}">\n</head>', 1)
            notes.append("noindex (empty)" if empty else "noindex lifted")
    elif empty:
        markup = markup.replace("</head>", f'<meta name="robots" content="{want}">\n</head>', 1)
        notes.append("noindex (empty)")

    # tags may end in ">", " />" or even '" >>' (an old generator typo), so
    # match up to the closing bracket loosely
    markup = set_tag(markup, r"<title>.*?</title>", f"<title>{esc(title)}</title>")
    markup = set_tag(markup, r'<meta name="description" content="[^"]*"[^>]*>', f'<meta name="description" content="{esc(desc)}">')
    markup = set_tag(markup, r'<meta property="og:title" content="[^"]*"[^>]*>', f'<meta property="og:title" content="{esc(title)}">')
    markup = set_tag(markup, r'<meta property="og:description" content="[^"]*"[^>]*>', f'<meta property="og:description" content="{esc(desc)}">')
    markup = set_tag(markup, r'<meta name="twitter:title" content="[^"]*"[^>]*>', f'<meta name="twitter:title" content="{esc(title)}">')
    markup = set_tag(markup, r'<meta name="twitter:description" content="[^"]*"[^>]*>', f'<meta name="twitter:description" content="{esc(desc)}">')
    notes.append(f"title {len(title)}c, desc {len(desc)}c ({genes}g/{agents}a/{trials}t)")

    # hero lede: the generator's one generic sentence sits right after the H1
    lede = build_lede(name, genes, agents, trials)
    new_markup = re.sub(r"(</h1>\s*)<p(?: class=\"lede\")?>.*?</p>", rf'\1<p class="lede">{lede}</p>', markup, count=1, flags=re.S)
    if new_markup != markup:
        markup = new_markup
        notes.append("lede")

    # section labels -> real headings
    n = len(re.findall(r'<div class="section-title">', markup))
    if n:
        markup = re.sub(r'<div class="section-title">(.*?)</div>', r'<h2 class="section-title">\1</h2>', markup, flags=re.S)
        notes.append(f"{n} section h2")

    # agent names in the disease-level search section are <h3 style="font-size:1rem">
    n = len(re.findall(r'<h3 style="font-size:1rem">', markup))
    if n:
        markup = re.sub(r'<h3 style="font-size:1rem">(.*?)</h3>', r'<p class="agent-name" style="font-size:1rem;font-weight:600;margin:0">\1</p>', markup, flags=re.S)
        notes.append(f"{n} agent h3->p")

    # Link back to the plain-language research note on the main site that
    # answers the same question, so the two hosts reinforce rather than
    # cannibalise each other.  Only rebuilt when the main-site checkout is
    # present (it is not in CI); otherwise the existing block is kept.
    if NOTE_MAP is not None:
        note = NOTE_MAP.get(page.stem)
        block = ""
        if note and not empty:
            url, question = note
            block = (f'{NOTE_START}<p class="note-link" style="margin:.75rem 0 0;font-size:.95rem">'
                     f'Plain-language summary: <a href="{esc(url)}">{esc(question)}</a></p>{NOTE_END}')
        if NOTE_START in markup:
            new_markup = re.sub(re.escape(NOTE_START) + r".*?" + re.escape(NOTE_END), lambda _m: block, markup, count=1, flags=re.S)
        elif block:
            new_markup = re.sub(r'(<p class="lede">.*?</p>)', lambda m: m.group(1) + block, markup, count=1, flags=re.S)
        else:
            new_markup = markup
        if new_markup != markup:
            markup = new_markup
            notes.append("note link")

    # A canonical (or og:url) naming a page that does not exist tells Google
    # to index a 404 and drop this page.  The generator derives those URLs
    # from db100 display slugs that often differ from the file name, so any
    # non-existent target is pointed back at this page itself.
    self_url = f"{ORIGIN}/chronic-disease-interventions/{page.name}"
    for pat in (r'(<link rel="canonical" href=")([^"]*)(")', r'(<meta property="og:url" content=")([^"]*)(")'):
        def fix(m: re.Match) -> str:
            url = m.group(2)
            if url.startswith(f"{ORIGIN}/chronic-disease-interventions/"):
                target = PAGES / url.rsplit("/", 1)[1]
                if not target.exists():
                    return m.group(1) + self_url + m.group(3)
            return m.group(0)
        new_markup = re.sub(pat, fix, markup, flags=re.I)
        if new_markup != markup:
            markup = new_markup
            notes.append("dead canonical/og:url -> self")

    twin = CANONICAL_TWINS.get(page.name)
    if twin:
        canon = f"{ORIGIN}/chronic-disease-interventions/{twin}"
        markup, k = re.subn(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{canon}">', markup, count=1, flags=re.I)
        if not k:
            markup = markup.replace("</head>", f'<link rel="canonical" href="{canon}">\n</head>', 1)
        notes.append(f"canonical -> {twin}")

    if markup != original and not dry:
        page.write_text(markup, encoding="utf-8")
    return notes if markup != original else ["unchanged"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", help="file names inside chronic-disease-interventions/")
    args = ap.parse_args()
    pages = sorted(PAGES.glob("*.html"))
    if args.only:
        pages = [p for p in pages if p.name in set(args.only)]
    pages = [p for p in pages if p.name != "index.html"]
    changed = 0
    for p in pages:
        notes = process(p, args.dry_run)
        if notes != ["unchanged"]:
            changed += 1
        print(f"{p.name}: {'; '.join(notes)}")
    print(f"\n{changed}/{len(pages)} pages {'would change' if args.dry_run else 'updated'}")


if __name__ == "__main__":
    main()
