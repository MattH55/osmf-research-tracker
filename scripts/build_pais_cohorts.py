#!/usr/bin/env python3
"""
Build + validate the PAIS cohort database.

Reads:  data/pais-cohort.schema.json, data/ref/*.json, data/cohorts/*.json
Writes: data/pais-cohorts-index.json   (compiled static index the frontend loads)
        data/pais-cohorts.csv           (one-click bulk CSV, works with JS disabled)
        pais-cohorts.html               (default cohort table + gap matrices, pre-rendered)
        pais-cohorts/<id>.html          (pre-rendered cohort detail pages)

Validation is part of the build: schema (Draft 2020-12) + cross-reference checks.
Exit code is non-zero on any failure so CI can block a merge.

Usage:
    python scripts/build_pais_cohorts.py            # validate + build
    python scripts/build_pais_cohorts.py --check    # validate only (CI)
"""
from __future__ import annotations
import json, glob, os, sys, html, csv, io

# Deterministic build label (do NOT use a wall-clock date: the CI "artifacts in
# sync" check rebuilds and diffs, so output must be reproducible across days).
BUILD_VERSION = "1.0.0-seed"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "data", "pais-cohort.schema.json")
COHORT_GLOB = os.path.join(ROOT, "data", "cohorts", "*.json")
PATHOGENS = os.path.join(ROOT, "data", "ref", "pathogens.json")
INSTRUMENTS = os.path.join(ROOT, "data", "ref", "instruments.json")

INDEX_OUT = os.path.join(ROOT, "data", "pais-cohorts-index.json")
CSV_OUT = os.path.join(ROOT, "data", "pais-cohorts.csv")
HTML_OUT = os.path.join(ROOT, "pais-cohorts.html")
DETAIL_DIR = os.path.join(ROOT, "pais-cohorts")

# ---- human-readable labels for enum values -------------------------------
LABELS = {
    "prospective_inception": "Prospective (inception)",
    "prospective_non_inception": "Prospective (non-inception)",
    "retrospective_cohort": "Retrospective cohort",
    "cross_sectional": "Cross-sectional",
    "case_control": "Case-control",
    "registry_linkage": "Registry linkage",
    "self_controlled": "Self-controlled",
    "survey": "Survey",
    "none": "None", "unexposed_matched": "Unexposed (matched)",
    "unexposed_unmatched": "Unexposed (unmatched)",
    "seronegative_contacts": "Seronegative contacts",
    "household_contacts": "Household contacts", "other_disease": "Other-disease",
    "self_control": "Self-control", "healthy_convenience": "Healthy convenience",
    "yes": "Yes", "partial": "Partial", "no": "No", "unclear": "Unclear",
    "virus": "Virus", "bacterium": "Bacterium", "protozoan": "Protozoan",
    "vaccine": "Vaccine", "mixed": "Mixed", "unknown": "Unknown",
    "not_reported": "Not reported", "not_applicable": "N/A",
    "yes_validated_instrument": "Yes (validated instrument)",
    "yes_single_item": "Yes (single item)",
}
# design columns for the gap matrix, in quality order (strongest first)
DESIGN_ORDER = ["prospective_inception", "prospective_non_inception", "retrospective_cohort",
                "registry_linkage", "self_controlled", "case_control", "cross_sectional", "survey"]
ACUTE_ORDER = ["yes", "no", "unclear", "not_applicable"]


def lab(v):
    if v is None:
        return "not reported"
    return LABELS.get(v, str(v).replace("_", " "))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def validate(cohorts, pathogens, instruments):
    """Schema + cross-reference validation. Returns list of error strings."""
    from jsonschema import Draft202012Validator
    schema = load_json(SCHEMA)
    v = Draft202012Validator(schema)
    errors = []
    pathogen_ids = {p["id"] for p in pathogens["pathogens"]}
    instrument_ids = {i["id"] for i in instruments["instruments"]}
    seen_ids = set()
    for path, d in cohorts:
        name = os.path.basename(path)
        for e in sorted(v.iter_errors(d), key=lambda e: list(e.path)):
            errors.append(f"{name}: schema: {'/'.join(map(str, e.path))}: {e.message}")
        cid = d.get("id")
        if cid in seen_ids:
            errors.append(f"{name}: duplicate cohort id '{cid}'")
        seen_ids.add(cid)
        if d.get("pathogen_id") not in pathogen_ids:
            errors.append(f"{name}: pathogen_id '{d.get('pathogen_id')}' not in pathogens.json")
        for iid in d.get("instruments", []):
            if iid not in instrument_ids:
                errors.append(f"{name}: instrument '{iid}' not in instruments.json")
        pub_ids = {p["id"] for p in d.get("publications", [])}
        for fnd in d.get("findings", []):
            if fnd.get("publication_id") not in pub_ids:
                errors.append(f"{name}: finding '{fnd.get('id')}' publication_id "
                              f"'{fnd.get('publication_id')}' not among this cohort's publications")
            iid = fnd.get("instrument_id")
            if iid is not None and iid not in instrument_ids:
                errors.append(f"{name}: finding '{fnd.get('id')}' instrument_id '{iid}' not in instruments.json")
    return errors


# ---- HTML helpers --------------------------------------------------------
def esc(s):
    return html.escape("" if s is None else str(s))


def na(v):
    """Render a value, marking not-reported/None distinctly for the UI."""
    if v is None:
        return '<span class="na">not reported</span>'
    return esc(lab(v))


CSS = """
:root{--bg:#fff;--fg:#1a1f26;--muted:#6b7480;--line:#e3e7ec;--card:#f7f9fb;
--accent:#0b6bcb;--warn:#b26a00;--good:#1a7f4b;--chip:#eef2f6;--zero:#faeaea;--zerofg:#a33}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--fg:#e6e9ee;--muted:#9aa4b0;
--line:#252b33;--card:#161b21;--accent:#5aa2ea;--warn:#e0a24a;--good:#5cc68d;
--chip:#1c232b;--zero:#2a1c1c;--zerofg:#e08a8a}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--fg)}
.wrap{max-width:1180px;margin:0 auto;padding:24px 18px 80px}
a{color:var(--accent)}h1{font-size:1.7rem;margin:.2em 0}
h2{font-size:1.2rem;margin:1.8em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.3em}
h3{font-size:1rem;margin:1.4em 0 .3em}
.lede{color:var(--muted);max-width:70ch}
.meta{font-size:.82rem;color:var(--muted);margin:.4em 0}
.chip{display:inline-block;background:var(--chip);border:1px solid var(--line);border-radius:999px;
padding:1px 9px;font-size:.78rem;margin:2px 3px 2px 0;white-space:nowrap}
.na{color:var(--muted);font-style:italic;font-size:.92em}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin:14px 0;padding:12px;
background:var(--card);border:1px solid var(--line);border-radius:10px}
.toolbar label{display:flex;flex-direction:column;font-size:.72rem;color:var(--muted);gap:2px}
.toolbar select,.toolbar input{font-size:.86rem;padding:4px 6px;background:var(--bg);color:var(--fg);
border:1px solid var(--line);border-radius:6px}
.btn{cursor:pointer;background:var(--accent);color:#fff;border:0;border-radius:6px;padding:6px 12px;font-size:.84rem}
.btn.sec{background:var(--chip);color:var(--fg);border:1px solid var(--line)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--card);position:sticky;top:0;cursor:pointer;white-space:nowrap}
tbody tr:hover{background:var(--card)}
.matrix td,.matrix th{text-align:center;padding:6px 8px}
.matrix th.row,.matrix td.row{text-align:left;font-weight:600}
.cell0{background:var(--zero);color:var(--zerofg)}
.cellN{font-weight:700}
.count{color:var(--muted);font-size:.85rem}
.back{font-size:.85rem}
.grid2{display:grid;grid-template-columns:180px 1fr;gap:2px 14px;font-size:.9rem}
.grid2 dt{color:var(--muted)}.grid2 dd{margin:0}
.warnbox{background:var(--zero);border:1px solid var(--line);border-left:3px solid var(--warn);
padding:10px 12px;border-radius:6px;margin:10px 0;font-size:.9rem}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:14px;font-size:.8rem;color:var(--muted)}
.pill{font-size:.72rem;padding:1px 7px;border-radius:999px;border:1px solid var(--line)}
.pill.good{color:var(--good)}.pill.no{color:var(--muted)}
"""


def cohort_row_cells(d, pmap):
    pth = pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"])
    n = d.get("n_analysed") or d.get("n_enrolled")
    spec = "banked" if d.get("specimens_collected") else "none"
    acute = d.get("acute_phase_specimens")
    spec_html = (f'<span class="pill good">banked</span>' if d.get("specimens_collected")
                 else '<span class="pill no">none</span>')
    if d.get("specimens_collected") and acute == "yes":
        spec_html += ' <span class="chip">acute-phase</span>'
    return {
        "name": f'<a href="pais-cohorts/{esc(d["id"])}.html">{esc(d["name"])}</a>',
        "pathogen": esc(pth), "pclass": lab(d["pathogen_class"]),
        "design": lab(d["design"]),
        "n": esc(n) if n is not None else '<span class="na">n/r</span>',
        "fu": esc(d.get("max_followup_months")) if d.get("max_followup_months") is not None else '<span class="na">n/r</span>',
        "control": lab(d["control_group"]),
        "denom": lab(d["denominator_defined"]),
        "spec": spec_html,
        # data-* for JS filtering
        "attrs": (f'data-pclass="{esc(d["pathogen_class"])}" data-design="{esc(d["design"])}" '
                  f'data-control="{esc(d["control_group"])}" data-denom="{esc(d["denominator_defined"])}" '
                  f'data-spec="{esc(spec)}" data-acute="{esc(acute)}" '
                  f'data-n="{esc(n if n is not None else "")}" data-fu="{esc(d.get("max_followup_months") if d.get("max_followup_months") is not None else "")}" '
                  f'data-name="{esc(d["name"].lower())}"'),
    }


def build_table(cohorts, pmap):
    cols = [("name", "Cohort"), ("pathogen", "Pathogen"), ("design", "Design"),
            ("n", "N"), ("fu", "Max follow-up (mo)"), ("control", "Control group"),
            ("denom", "Denominator"), ("spec", "Specimens")]
    head = "".join(f'<th data-sort="{k}">{esc(t)}</th>' for k, t in cols)
    rows = []
    for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()):
        c = cohort_row_cells(d, pmap)
        tds = "".join(f"<td>{c[k]}</td>" for k, _ in cols)
        rows.append(f'<tr {c["attrs"]}>{tds}</tr>')
    return (f'<div class="tablewrap"><table id="cohorts"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def build_matrix(cohorts, pmap, col_order, col_key, title, desc):
    # rows = pathogens present, cols = col_order values
    used_pathogens = []
    for _, d in cohorts:
        if d["pathogen_id"] not in used_pathogens:
            used_pathogens.append(d["pathogen_id"])
    counts = {}
    for _, d in cohorts:
        counts.setdefault(d["pathogen_id"], {})
        key = d.get(col_key)
        counts[d["pathogen_id"]][key] = counts[d["pathogen_id"]].get(key, 0) + 1
    head = '<th class="row"></th>' + "".join(f"<th>{esc(lab(c))}</th>" for c in col_order)
    body = []
    for pid in used_pathogens:
        pname = pmap.get(pid, {}).get("name", pid)
        cells = [f'<td class="row">{esc(pname)}</td>']
        for c in col_order:
            n = counts.get(pid, {}).get(c, 0)
            cls = "cell0" if n == 0 else "cellN"
            cells.append(f'<td class="{cls}">{n if n else ""}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<h3>{esc(title)}</h3><p class="meta">{esc(desc)}</p>'
            f'<div class="tablewrap"><table class="matrix"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def facet_select(name, label, values):
    opts = '<option value="">all</option>' + "".join(
        f'<option value="{esc(v)}">{esc(lab(v))}</option>' for v in values)
    return f'<label>{esc(label)}<select data-facet="{esc(name)}">{opts}</select></label>'


PAGE_JS = r"""
<script>
(function(){
 var tb=document.getElementById('cohorts'); if(!tb) return;
 var rows=[].slice.call(tb.tBodies[0].rows);
 var facets=[].slice.call(document.querySelectorAll('[data-facet]'));
 var q=document.getElementById('q');
 function apply(){
   var f={}; facets.forEach(function(s){ if(s.value) f[s.dataset.facet]=s.value; });
   var term=(q&&q.value||'').toLowerCase();
   var shown=0;
   rows.forEach(function(r){
     var ok=true;
     for(var k in f){ if(r.getAttribute('data-'+k)!==f[k]){ ok=false; break; } }
     if(ok&&term){ ok=r.getAttribute('data-name').indexOf(term)>-1; }
     r.style.display=ok?'':'none'; if(ok)shown++;
   });
   var c=document.getElementById('count'); if(c)c.textContent=shown+' of '+rows.length+' cohorts';
 }
 facets.forEach(function(s){s.addEventListener('change',apply);});
 if(q)q.addEventListener('input',apply);
 // sorting
 var ths=[].slice.call(tb.tHead.rows[0].cells); var dir={};
 ths.forEach(function(th){ th.addEventListener('click',function(){
   var key=th.dataset.sort, num=(key==='n'||key==='fu');
   dir[key]=!dir[key]; var s=dir[key]?1:-1;
   var vis=rows.slice();
   vis.sort(function(a,b){
     var av=a.getAttribute('data-'+ (key==='name'?'name':key))||'';
     var bv=b.getAttribute('data-'+ (key==='name'?'name':key))||'';
     if(key==='n'||key==='fu'){ av=parseFloat(a.getAttribute('data-'+key)); bv=parseFloat(b.getAttribute('data-'+key));
       if(isNaN(av))av=-1; if(isNaN(bv))bv=-1; return (av-bv)*s; }
     if(key==='pathogen'||key==='design'||key==='control'||key==='denom'){ av=a.cells[0].textContent; bv=b.cells[0].textContent; }
     return av<bv?-s:av>bv?s:0;
   });
   var body=tb.tBodies[0]; vis.forEach(function(r){body.appendChild(r);});
 });});
 // export
 function dl(name,txt,type){ var b=new Blob([txt],{type:type}); var u=URL.createObjectURL(b);
   var a=document.createElement('a'); a.href=u; a.download=name; a.click(); URL.revokeObjectURL(u); }
 var ej=document.getElementById('exp-json'), ec=document.getElementById('exp-csv');
 if(ej)ej.addEventListener('click',function(){ fetch('data/pais-cohorts-index.json').then(function(r){return r.text();}).then(function(t){dl('pais-cohorts-index.json',t,'application/json');}); });
 if(ec)ec.addEventListener('click',function(){ fetch('data/pais-cohorts.csv').then(function(r){return r.text();}).then(function(t){dl('pais-cohorts.csv',t,'text/csv');}); });
 apply();
})();
</script>
"""


def build_main_page(cohorts, pmap, generated):
    pclasses = sorted({d["pathogen_class"] for _, d in cohorts})
    designs = [x for x in DESIGN_ORDER if x in {d["design"] for _, d in cohorts}]
    controls = sorted({d["control_group"] for _, d in cohorts})
    denoms = ["yes", "partial", "no", "unclear"]
    toolbar = (
        '<div class="toolbar">'
        '<label>Search<input id="q" type="search" placeholder="cohort name…"></label>'
        + facet_select("pclass", "Pathogen class", pclasses)
        + facet_select("design", "Design", designs)
        + facet_select("control", "Control group", controls)
        + facet_select("denom", "Denominator", denoms)
        + facet_select("spec", "Specimens", ["banked", "none"])
        + facet_select("acute", "Acute-phase spec.", ["yes", "no", "unclear", "not_applicable"])
        + '<span style="flex:1"></span>'
        '<button class="btn sec" id="exp-json">Export JSON</button>'
        '<button class="btn sec" id="exp-csv">Export CSV</button>'
        '</div>'
    )
    table = build_table(cohorts, pmap)
    m1 = build_matrix(cohorts, pmap, designs, "design",
                      "Gap matrix — pathogen × study design",
                      "Cell = number of cohorts. Red (empty) cells mark pathogen/design combinations where no cohort yet exists — the evidence gaps this database exists to expose.")
    m2 = build_matrix(cohorts, pmap, ACUTE_ORDER, "acute_phase_specimens",
                      "Gap matrix — pathogen × acute-phase specimens banked",
                      "Cell = number of cohorts. Acute-phase specimens (drawn during infection, before the outcome is known) are what make a cohort useful for mechanism studies; empty cells show where they are missing.")
    body = f"""<div class="wrap">
<p class="back"><a href="index.html">← Research tracker</a></p>
<h1>PAIS Cohort Database</h1>
<p class="lede">A catalogue of <strong>cohorts</strong> (study populations followed for post-acute infection syndrome outcomes), not patients and not publications. The unit of record is the cohort, so that one cohort's many papers do not overstate how much independent evidence exists. The point of the database is to make the <em>design</em> of each study — denominator, controls, timepoints, specimens — machine-readable, so the incomparability of the literature and its gaps become visible.</p>
<p class="meta">{len(cohorts)} cohorts · seed release · every field human-verified against source · data licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> · <a href="data/pais-cohort.schema.json">schema</a> · <a href="pais-cohort-database-spec.md">spec</a></p>
<div class="warnbox">This is a <strong>seed</strong> of {len(cohorts)} design-verified cohorts, not a complete census. It deliberately mixes strong designs (prospective inception cohorts with unexposed controls) and weak ones (self-selected online surveys) so the gap matrices below are honest. Contributions are made as pull requests; schema validation runs in CI and blocks merges that break it. No pooled estimates or quality scores are computed — filter the design fields and judge for yourself.</div>
{toolbar}
<p class="count" id="count">{len(cohorts)} cohorts</p>
{table}
<h2>Gap matrices</h2>
{m1}
{m2}
<footer>
<p>Build {generated}, compiled by <code>scripts/build_pais_cohorts.py</code>. Cohort table and detail pages are pre-rendered and work with JavaScript disabled; filtering, sorting and export are progressive enhancements. No analytics, no third-party fonts or scripts.</p>
<p>Bulk export: <a href="data/pais-cohorts-index.json">JSON</a> · <a href="data/pais-cohorts.csv">CSV</a>. Per-cohort permalinks under <code>pais-cohorts/&lt;id&gt;.html</code>.</p>
</footer>
</div>{PAGE_JS}"""
    return html_doc("PAIS Cohort Database", body)


def html_doc(title, body):
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{body}</body></html>")


def dl_list(items):
    return "<dl class=grid2>" + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"


def build_detail(d, pmap, imap):
    pth = pmap.get(d["pathogen_id"], {})
    identity = dl_list([
        ("Cohort id", f"<code>{esc(d['id'])}</code>"),
        ("Aliases", ", ".join(map(esc, d.get("aliases", []))) or '<span class="na">none</span>'),
        ("Outbreak / event", na(d.get("outbreak_event"))),
        ("Pathogen", f"{esc(pth.get('name', d['pathogen_id']))} ({lab(d['pathogen_class'])})"),
        ("Exposure ascertainment", na(d.get("exposure_ascertainment"))),
    ])
    design = dl_list([
        ("Design", lab(d["design"])),
        ("Denominator defined", lab(d["denominator_defined"])),
        ("Denominator method", na(d.get("denominator_method"))),
        ("Recruitment source", lab(d["recruitment_source"])),
        ("Time zero", esc(d.get("time_zero_definition")) + f' ({lab(d.get("time_zero_precision"))})'),
        ("Control group", lab(d["control_group"])),
        ("Matching variables", ", ".join(map(esc, d.get("control_matching_variables", []))) or '<span class="na">none</span>'),
    ])
    size = dl_list([
        ("Source population", na(d.get("n_source_population"))),
        ("Enrolled", na(d.get("n_enrolled"))),
        ("Analysed", na(d.get("n_analysed"))),
        ("Max follow-up (months)", na(d.get("max_followup_months"))),
        ("Follow-up points", ", ".join(f"{f['months']}mo" for f in d.get("followups", [])) or '<span class="na">not reported</span>'),
    ])
    instruments = ", ".join(imap.get(i, {}).get("name", i) for i in d.get("instruments", [])) or '<span class="na">none listed</span>'
    measure = dl_list([
        ("Instruments", instruments),
        ("Case definition", lab(d["case_definition"])),
        ("PEM assessed", lab(d["pem_assessed"])),
        ("Objective measures", ", ".join(lab(x) for x in d.get("objective_measures", [])) or '<span class="na">none</span>'),
    ])
    spec = dl_list([
        ("Specimens collected", "Yes" if d.get("specimens_collected") else "No"),
        ("Specimen types", ", ".join(map(esc, d.get("specimen_types", []))) or '<span class="na">none</span>'),
        ("Acute-phase specimens", lab(d["acute_phase_specimens"])),
        ("Storage", na(d.get("storage"))),
        ("Biobank status", lab(d["biobank_status"])),
        ("Consent for future use", lab(d.get("consent_future_use"))),
        ("External access", lab(d.get("external_access"))),
    ])
    prov = dl_list([
        ("Registration", na(d.get("registration_id"))),
        ("Funders", ", ".join(map(esc, d.get("funders", []))) or '<span class="na">not reported</span>'),
        ("Conflicts", na(d.get("conflicts"))),
        ("Data availability", na(d.get("data_availability"))),
    ])
    # findings table
    if d.get("findings"):
        fh = "".join(f"<th>{esc(h)}</th>" for h in
                     ["Outcome", "Timepoint (mo)", "n/N", "%", "95% CI", "Effect", "As worded", "Source"])
        frows = []
        for f in d["findings"]:
            nN = (f"{f['n_with_outcome']}/{f['n_assessed']}" if f.get("n_with_outcome") is not None and f.get("n_assessed") is not None
                  else (f"–/{f['n_assessed']}" if f.get("n_assessed") is not None else '<span class="na">n/r</span>'))
            pct = f"{f['percent']}%" if f.get("percent") is not None else '<span class="na">n/r</span>'
            ci = (f"{f['ci_low']}–{f['ci_high']}" if f.get("ci_low") is not None and f.get("ci_high") is not None else "")
            eff = (f"{lab(f['effect_type'])} {f['effect_estimate']}" if f.get("effect_estimate") is not None and f.get("effect_type") != "none" else "")
            frows.append("<tr>" + "".join(f"<td>{c}</td>" for c in [
                lab(f["outcome"]), na(f.get("timepoint_months")), nN, pct, esc(ci) or "—",
                esc(eff) or "—", esc(f.get("outcome_verbatim")), esc(f.get("source_locator"))]) + "</tr>")
        findings = (f'<div class="tablewrap"><table><thead><tr>{fh}</tr></thead>'
                    f'<tbody>{"".join(frows)}</tbody></table></div>')
    else:
        findings = '<p class="na">No findings extracted yet — contributions welcome via pull request.</p>'
    # publications
    pubs = []
    for p in d.get("publications", []):
        ident = (f'PMID <a href="https://pubmed.ncbi.nlm.nih.gov/{esc(p["pmid"])}/">{esc(p["pmid"])}</a>' if p.get("pmid") else "")
        if p.get("doi"):
            ident += (" · " if ident else "") + f'DOI <a href="https://doi.org/{esc(p["doi"])}">{esc(p["doi"])}</a>'
        primary = ' <span class="chip">primary cohort paper</span>' if p.get("is_primary_cohort_paper") else ""
        oa = ' <span class="pill good">open access</span>' if p.get("open_access") else ""
        pubs.append(f'<li>{esc(p.get("authors"))} ({esc(p["year"])}). <strong>{esc(p["title"])}</strong>. '
                    f'<em>{esc(p.get("journal"))}</em>. {ident}{primary}{oa}</li>')
    pubs_html = "<ul>" + "".join(pubs) + "</ul>"
    notes = f'<div class="warnbox"><strong>Design notes & limitations.</strong> {esc(d.get("notes"))}</div>' if d.get("notes") else ""
    body = f"""<div class="wrap">
<p class="back"><a href="../pais-cohorts.html">← All cohorts</a></p>
<h1>{esc(d['name'])}</h1>
<p class="meta"><a href="../data/cohorts/{esc(d['id'])}.json">source record (JSON)</a> · licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a></p>
{notes}
<h2>Identity & trigger</h2>{identity}
<h2>Design</h2>{design}
<h2>Size & attrition</h2>{size}
<h2>Measurement</h2>{measure}
<h2>Biospecimens</h2>{spec}
<h2>Findings</h2>{findings}
<h2>Publications</h2>{pubs_html}
<h2>Provenance</h2>{prov}
<footer><p>PAIS Cohort Database · <a href="../pais-cohorts.html">back to table</a></p></footer>
</div>"""
    return html_doc(f"{d['name']} — PAIS Cohort", body)


def cohort_to_csv_rows(cohorts, pmap):
    header = ["id", "name", "pathogen", "pathogen_class", "design", "denominator_defined",
              "control_group", "recruitment_source", "n_enrolled", "n_analysed",
              "max_followup_months", "case_definition", "pem_assessed", "specimens_collected",
              "acute_phase_specimens", "biobank_status", "external_access", "n_publications", "n_findings"]
    rows = [header]
    for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()):
        rows.append([
            d["id"], d["name"], pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"]),
            d["pathogen_class"], d["design"], d["denominator_defined"], d["control_group"],
            d["recruitment_source"], d.get("n_enrolled"), d.get("n_analysed"),
            d.get("max_followup_months"), d["case_definition"], d["pem_assessed"],
            d["specimens_collected"], d["acute_phase_specimens"], d["biobank_status"],
            d.get("external_access"), len(d.get("publications", [])), len(d.get("findings", []))])
    return rows


def main():
    check_only = "--check" in sys.argv
    pathogens = load_json(PATHOGENS)
    instruments = load_json(INSTRUMENTS)
    cohorts = [(p, load_json(p)) for p in sorted(glob.glob(COHORT_GLOB))]
    if not cohorts:
        print("No cohort files found.", file=sys.stderr); sys.exit(1)

    errors = validate(cohorts, pathogens, instruments)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} error(s)):", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)
    print(f"Validation OK: {len(cohorts)} cohorts, "
          f"{sum(len(d.get('publications', [])) for _, d in cohorts)} publications, "
          f"{sum(len(d.get('findings', [])) for _, d in cohorts)} findings.")
    if check_only:
        return

    pmap = {p["id"]: p for p in pathogens["pathogens"]}
    imap = {i["id"]: i for i in instruments["instruments"]}
    generated = BUILD_VERSION

    # compiled index
    index = {
        "schema_version": "1.0.0",
        "generated": generated,
        "license": "CC BY 4.0",
        "pathogens": pathogens["pathogens"],
        "instruments": instruments["instruments"],
        "cohorts": [d for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower())],
    }
    with open(INDEX_OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # bulk CSV
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in cohort_to_csv_rows(cohorts, pmap):
        w.writerow(r)
    with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())

    # main page
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(build_main_page(cohorts, pmap, generated))

    # detail pages
    os.makedirs(DETAIL_DIR, exist_ok=True)
    for _, d in cohorts:
        with open(os.path.join(DETAIL_DIR, f"{d['id']}.html"), "w", encoding="utf-8") as f:
            f.write(build_detail(d, pmap, imap))

    print(f"Built: {os.path.relpath(INDEX_OUT, ROOT)}, {os.path.relpath(CSV_OUT, ROOT)}, "
          f"{os.path.relpath(HTML_OUT, ROOT)}, {len(cohorts)} detail pages in {os.path.relpath(DETAIL_DIR, ROOT)}/")


if __name__ == "__main__":
    main()
