#!/usr/bin/env python3
"""Unified chrome for every public research-tracker page (idempotent).

For each page this:
  * links css/osmf-ui.css (+ Inter / Fraunces) as the LAST stylesheet,
  * adds class "osmf-ui" to <body>,
  * replaces the page's own top navigation with the shared header,
  * replaces the page's own site footer (and the legacy network banner /
    donate block that duplicated it) with the shared footer.

All insertions sit between OSMF_UI_* sentinel comments, so re-running
replaces rather than duplicates.  Run after every generator, before
build_site_seo.py:

    python scripts/apply_osmf_ui.py            # apply
    python scripts/apply_osmf_ui.py --check    # report only
    python scripts/apply_osmf_ui.py --only compare/long-covid-vs-me-cfs.html
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIRS = ("biomarkers", "compare", "trials", "pairs", "digest", "reports", "tools", "embed",
               "chronic-disease-interventions", "disease-intelligence", "ntd", "pais-cohorts", "agents")
EXCLUDED_NAMES = {"agents-local.html", "clinical_trials-local.html"}
SKIP_PARTS = {"ntd-pipeline", "__pycache__", "hospital-ranking", "med-freedom-map", "data", "files"}
# iframe-able / embedded documents keep their own minimal chrome
SKIP_REL = {"embed/latest-research.html"}

PAYPAL = "https://www.paypal.com/ncp/payment/A2MK3BCVE4X7C"

NAV = [  # href, label, section prefixes that mark it current, minor (hidden on mid widths)
    ("/", "Conditions", ("index.html", "long-covid.html", "me-cfs.html", "pacvs.html", "pots.html",
                         "mcas.html", "lyme.html", "gulf-war-illness.html", "other-post-viral.html",
                         "post-viral-illness.html", "compare/"), False),
    ("/biomarker-atlas.html", "Biomarkers", ("biomarker", "biomarkers/", "-biomarkers.html", "long-covid-endotypes",
                                             "long-covid-hypotheses", "long-covid-metabolites",
                                             "long-covid-neurotransmitters", "long-covid-viral-persistence"), False),
    ("/clinical_trials.html", "Trials", ("clinical_trials", "trials/"), False),
    ("/agents.html", "Therapeutics", ("agents", "candidate-therapeutics", "therapeutic", "pairs/",
                                      "chronic-disease-interventions/", "disease-intelligence/"), False),
    ("/tools/repurposing-explorer.html", "Repurposing", ("tools/repurposing",), False),
    ("/pais-cohorts.html", "Cohorts", ("pais-",), True),
    ("/digest/index.html", "Digest", ("digest/", "reports/"), True),
]

MARK_SVG = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.5 3.5h5v6h6v5h-6v6h-5v-6h-6v-5h6z" '
            'fill="#ffb547"/><circle cx="12" cy="12" r="2.1" fill="#0e1444"/></svg>')

HEAD_START, HEAD_END = "<!-- OSMF_UI_HEAD_START -->", "<!-- OSMF_UI_HEAD_END -->"
HDR_START, HDR_END = "<!-- OSMF_UI_HEADER_START -->", "<!-- OSMF_UI_HEADER_END -->"
FTR_START, FTR_END = "<!-- OSMF_UI_FOOTER_START -->", "<!-- OSMF_UI_FOOTER_END -->"

HEAD_BLOCK = f"""{HEAD_START}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT@0,9..144,400..600,50;1,9..144,400..600,50&family=Inter:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="/css/osmf-ui.css">
{HEAD_END}"""


def current_href(rel: str) -> str | None:
    def hit(p: str) -> bool:
        if p.startswith("-"):                 # suffix family, root pages only (e.g. -biomarkers.html)
            return "/" not in rel and rel.endswith(p)
        return rel.startswith(p)              # exact page, page-name prefix, or directory
    for href, _label, prefixes, _minor in NAV:
        if any(hit(p) for p in prefixes):
            return href
    return None


def header_html(rel: str) -> str:
    cur = current_href(rel)
    links, mobile = [], []
    for href, label, _p, minor in NAV:
        aria = ' aria-current="page"' if href == cur else ""
        cls = ' class="osmf-nav__minor"' if minor else ""
        links.append(f'<a href="{href}"{cls}{aria}>{label}</a>')
        mobile.append(f'<a href="{href}"{aria}>{label}</a>')
    brand = (f'<a class="osmf-brand" href="/" aria-label="Open Source Medicine Research Tracker home">'
             f'<span class="osmf-brand__mark">{MARK_SVG}</span>'
             f'<span class="osmf-brand__text"><span class="osmf-brand__name">Open Source Medicine</span>'
             f'<span class="osmf-brand__sub">Research Tracker</span></span></a>')
    cta = f'<a class="osmf-cta" href="{PAYPAL}" rel="noopener">Support our work</a>'
    return (f'{HDR_START}\n<div class="osmf-header" role="banner"><div class="osmf-header__in">{brand}'
            f'<div class="osmf-nav" role="navigation" aria-label="Primary">{"".join(links)}</div>{cta}'
            f'<details class="osmf-menu"><summary aria-label="Open menu"><span></span></summary>'
            f'<div class="osmf-menu__panel" role="navigation" aria-label="Mobile">{"".join(mobile)}'
            f'<a href="https://opensourcemed.info/">opensourcemed.info</a>{cta}</div></details>'
            f'</div></div>\n{HDR_END}')


FOOTER = f"""{FTR_START}
<div class="osmf-footer" role="contentinfo">
  <div class="osmf-footer__cta">
    <div>
      <h2>The research patients need, <em>made open source.</em></h2>
      <p>Every page here is built from public data and refreshed daily. Get the week's new studies and trial changes in one email.</p>
    </div>
    <div class="osmf-footer__actions">
      <a class="osmf-cta" href="https://opensourcemed.substack.com/subscribe?utm_source=tracker&amp;utm_medium=footer" rel="noopener">Get the weekly digest</a>
      <a class="osmf-btn-ghost" href="{PAYPAL}" rel="noopener">Support our work</a>
    </div>
  </div>
  <div class="osmf-footer__grid">
    <div class="osmf-footer__about">
      <a class="osmf-brand" href="/"><span class="osmf-brand__mark">{MARK_SVG}</span><span class="osmf-brand__text"><span class="osmf-brand__name">Open Source Medicine</span><span class="osmf-brand__sub">Research Tracker</span></span></a>
      <p>An independent nonprofit research foundation mapping biomarkers, trials and repurposed medicines for post-viral and chronic disease. Every claim links to its source.</p>
    </div>
    <div><h3>Conditions</h3><ul>
      <li><a href="/long-covid.html">Long COVID</a></li><li><a href="/me-cfs.html">ME/CFS</a></li>
      <li><a href="/pacvs.html">PACVS</a></li><li><a href="/pots.html">POTS</a></li>
      <li><a href="/lyme.html">Lyme / PTLDS</a></li><li><a href="/compare/index.html">Compare conditions</a></li>
    </ul></div>
    <div><h3>Data</h3><ul>
      <li><a href="/biomarker-atlas.html">Biomarker atlases</a></li><li><a href="/biomarkers/index.html">Marker pages</a></li>
      <li><a href="/trials/index.html">Recruiting trials</a></li><li><a href="/agents.html">Therapeutic agents</a></li>
      <li><a href="/chronic-disease-interventions/index.html">Chronic disease drugs</a></li><li><a href="/pais-cohorts.html">Cohort database</a></li>
    </ul></div>
    <div><h3>Tools</h3><ul>
      <li><a href="/tools/biomarker-lookup.html">Biomarker lookup</a></li><li><a href="/tools/repurposing-explorer.html">Repurposing explorer</a></li>
      <li><a href="/clinical_trials.html">Trial finder</a></li><li><a href="/embed/index.html">Embed widget</a></li>
      <li><a href="/digest/index.html">Weekly digest</a></li><li><a href="/reports/index.html">Evidence reports</a></li>
    </ul></div>
    <div><h3>Foundation</h3><ul>
      <li><a href="https://opensourcemed.info/">opensourcemed.info</a></li><li><a href="https://opensourcemed.info/team.html">Team</a></li>
      <li><a href="https://opensourcemed.info/authors/">Authors</a></li><li><a href="https://opensourcemed.info/editorial-policy.html">Editorial policy</a></li>
      <li><a href="https://opensourcemed.info/contact.html">Contact</a></li><li><a href="/digest/feed.xml">RSS feed</a></li>
    </ul></div>
  </div>
  <div class="osmf-footer__base">
    <span>© Open Source Medicine Foundation MTÜ · Tallinn, Estonia · Data CC BY 4.0</span>
    <span>Research information, not medical advice. Discuss treatment decisions with a qualified clinician.</span>
  </div>
</div>
{FTR_END}"""

# ── legacy chrome patterns ────────────────────────────────────────────────
# Top navigations: the first <nav> after <body> that is a site nav (not a
# breadcrumb / table-of-contents).  Also a few templates wrap nav in <header>.
SITE_NAV_RE = re.compile(r"<nav\b(?![^>]*(?:breadcrumb|crumb|aria-label=\"(?:Breadcrumb|Contents|Table of contents|Pagination)))[^>]*>.*?</nav>", re.S | re.I)
HEADER_WRAP_RE = re.compile(r"<header\b[^>]*class=\"[^\"]*(?:site-header|topbar|top-bar|navbar)[^\"]*\"[^>]*>.*?</header>", re.S | re.I)
LEGACY_BLOCKS = [
    re.compile(r"<!-- OSMF Network Component -->\s*<section class=\"osmf-network-banner\">.*?</section>", re.S),
    re.compile(r"<section class=\"osmf-network-banner\">.*?</section>", re.S),
    re.compile(r"<div class=\"donate-section\">.*?</div>\s*</div>\s*</div>", re.S),
]
DONATE_RE = re.compile(r"<div class=\"donate-section\">(?:(?!<div class=\"donate-section\">).)*?<div class=\"donate-btns\">.*?</div>\s*</div>", re.S)
SITE_FOOTER_RE = re.compile(r"<footer\s+class=\"?(?:osmf-network-footer|site|osmf)\"?>.*?</footer>", re.S)
SCRIPT_RE = re.compile(r"<script[^>]*>(?:(?!</script>).)*</script>", re.S)
STATUS_BANNER_RE = re.compile(r"\s*<div style=\"background:#fef3c7;[^\"]*\">Status: In preparation\.[^<]*</div>", re.S)


def public_pages() -> list[Path]:
    pages = [p for p in ROOT.glob("*.html") if p.name not in EXCLUDED_NAMES]
    for d in PUBLIC_DIRS:
        base = ROOT / d
        if base.exists():
            pages.extend(p for p in base.rglob("*.html") if not (SKIP_PARTS & set(p.relative_to(ROOT).parts)))
    return sorted(set(pages))


def is_redirect(markup: str) -> bool:
    return bool(re.search(r"<meta\b[^>]*http-equiv\s*=\s*['\"]?refresh", markup, re.I))


def replace_block(markup: str, start: str, end: str, block: str) -> tuple[str, bool]:
    if start in markup and end in markup:
        pre, rest = markup.split(start, 1)
        _old, post = rest.split(end, 1)
        return pre + block + post, True
    return markup, False


def strip_top_nav(body: str) -> str:
    """Remove the legacy site navigation that sits before the page content."""
    # only look in the first chunk of the body (before main content starts)
    cut = len(body)
    for marker in ("<main", "<h1", 'class="hero', 'class="page-hero', "<article"):
        i = body.find(marker)
        if i != -1:
            cut = min(cut, i)
    head, rest = body[:cut], body[cut:]
    head = HEADER_WRAP_RE.sub("", head, count=1)
    m = SITE_NAV_RE.search(head)
    if m and m.group(0).count("<a ") >= 3:
        head = head[:m.start()] + head[m.end():]
    head = STATUS_BANNER_RE.sub("", head)
    return head + rest


def strip_footer(body: str) -> str:
    for rx in (LEGACY_BLOCKS[0], LEGACY_BLOCKS[1], DONATE_RE):
        body = rx.sub("", body)
    # known site-footer classes go wherever they are
    body = SITE_FOOTER_RE.sub("", body)
    # a bare/unknown LAST <footer> is the site footer only if nothing but
    # scripts and closing tags follow it; footers inside cards stay
    idx = body.rfind("<footer")
    if idx != -1:
        end = body.find("</footer>", idx)
        if end != -1:
            after = SCRIPT_RE.sub("", body[end + len("</footer>"):])
            if len(re.sub(r"</?(?:div|main|section|body|html)[^>]*>|\s+", "", after)) < 400:
                body = body[:idx] + body[end + len("</footer>"):]
    return body


def process(page: Path, check: bool) -> bool:
    rel = page.relative_to(ROOT).as_posix()
    if rel in SKIP_REL:
        return False
    original = page.read_text(encoding="utf-8", errors="replace")
    markup = original
    if is_redirect(markup) or "<body" not in markup:
        return False

    # 1. head assets (last thing in <head> so it wins the cascade)
    markup, done = replace_block(markup, HEAD_START, HEAD_END, HEAD_BLOCK)
    if not done:
        markup = markup.replace("</head>", HEAD_BLOCK + "\n</head>", 1)

    # 2. body class
    def add_class(m: re.Match) -> str:
        tag = m.group(0)
        if "osmf-ui" in tag:
            return tag
        if re.search(r'class="', tag):
            return re.sub(r'class="', 'class="osmf-ui ', tag, count=1)
        return tag[:-1] + ' class="osmf-ui">'
    markup = re.sub(r"<body\b[^>]*>", add_class, markup, count=1)

    # 3. header
    hdr = header_html(rel)
    markup, done = replace_block(markup, HDR_START, HDR_END, hdr)
    if not done:
        pre, body = re.split(r"(?<=>)", markup.split("<body", 1)[1], maxsplit=1)
        body = strip_top_nav(body)
        markup = markup.split("<body", 1)[0] + "<body" + pre + "\n" + hdr + body

    # 4. footer
    markup, done = replace_block(markup, FTR_START, FTR_END, FOOTER)
    if not done:
        head, tail = markup.rsplit("</body>", 1)
        head = strip_footer(head)
        # keep page scripts after the footer working: insert footer before trailing <script>s
        # only a run of CONSECUTIVE trailing <script> blocks (a script body may
        # not span past its own </script>), so the footer lands after content
        m = re.search(r"(\s*(?:<script\b[^>]*>(?:(?!</script>).)*</script>\s*)*)$", head, re.S)
        insert_at = m.start() if m else len(head)
        markup = head[:insert_at] + "\n" + FOOTER + head[insert_at:] + "</body>" + tail

    if markup != original:
        if not check:
            page.write_text(markup, encoding="utf-8")
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    pages = public_pages()
    if args.only:
        wanted = set(args.only)
        pages = [p for p in pages if p.relative_to(ROOT).as_posix() in wanted]
    changed = sum(process(p, args.check) for p in pages)
    print(f"osmf-ui: {len(pages)} pages scanned, {changed} {'would change' if args.check else 'updated'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
