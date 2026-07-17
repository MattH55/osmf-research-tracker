"""Attach regulation URLs to every access cell (procedure × jurisdiction).

Priority:
1. Pair-specific programme / statute links
2. Jurisdiction regulation profile key_statutes (with URLs)
3. Default regulator portal for that jurisdiction
4. Sources already stored on the access row
"""
from .seed_prohibitions import all_jurisdiction_regulation, JUR_PSYCHEDELIC_LAW


def L(title, url, citation=None):
    d = {"title": title, "url": url}
    if citation:
        d["citation"] = citation
    return d


# Default official portals by jurisdiction
JUR_DEFAULT_LINKS = {
    "jur-us-federal": [
        L("FDA — Drugs & biologics", "https://www.fda.gov/drugs"),
        L("DEA — Controlled substance schedules", "https://www.dea.gov/drug-information/drug-scheduling"),
        L("ClinicalTrials.gov", "https://clinicaltrials.gov"),
    ],
    "jur-us-or": [
        L("Oregon Psilocybin Services (OHA)", "https://www.oregon.gov/oha/PH/PREVENTIONWELLNESS/Pages/Psilocybin-Services.aspx"),
        L("OPS Licensee Directory", "https://psilocybin.oregon.gov/license-directory"),
        L("Oregon Death with Dignity Act overview", "https://www.oregon.gov/oha/ph/providerpartnerresources/evaluationresearch/deathwithdignityact/pages/index.aspx"),
    ],
    "jur-us-co": [
        L("Colorado Natural Medicine (DORA)", "https://dpo.colorado.gov/NaturalMedicine"),
        L("Prop 122 / Natural Medicine Health Act materials", "https://leg.colorado.gov"),
    ],
    "jur-us-ca": [
        L("California Department of Cannabis Control", "https://cannabis.ca.gov"),
        L("CA Board of Pharmacy", "https://www.pharmacy.ca.gov"),
    ],
    "jur-us-tx": [
        L("Texas State Board of Pharmacy", "https://www.pharmacy.texas.gov"),
        L("Texas Medical Board", "https://www.tmb.state.tx.us"),
    ],
    "jur-us-fl": [
        L("Florida Board of Medicine", "https://flboardofmedicine.gov"),
        L("Florida Department of Health", "https://www.floridahealth.gov"),
    ],
    "jur-uk": [
        L("MHRA — Medicines & Healthcare products", "https://www.gov.uk/government/organisations/medicines-and-healthcare-products-regulatory-agency"),
        L("Controlled drugs list (UK)", "https://www.gov.uk/government/publications/controlled-drugs-list--2"),
        L("Misuse of Drugs Act 1971", "https://www.legislation.gov.uk/ukpga/1971/38/contents"),
        L("NICE guidance", "https://www.nice.org.uk"),
    ],
    "jur-de": [
        L("BfArM — Federal Institute for Drugs and Medical Devices", "https://www.bfarm.de/EN/Home/home_node.html"),
        L("BtMG (Narcotics Act) — Gesetze im Internet", "https://www.gesetze-im-internet.de/btmg_1981/"),
        L("G-BA (joint federal committee)", "https://www.g-ba.de"),
    ],
    "jur-fr": [
        L("ANSM — Agence nationale de sécurité du médicament", "https://ansm.sante.fr"),
        L("Légifrance — Code de la santé publique", "https://www.legifrance.gouv.fr"),
    ],
    "jur-es": [
        L("AEMPS — Agencia Española de Medicamentos", "https://www.aemps.gob.es"),
        L("BOE — Spanish Official State Gazette", "https://www.boe.es"),
    ],
    "jur-nl": [
        L("IGJ — Health and Youth Care Inspectorate", "https://www.igj.nl"),
        L("Government.nl — Opium Act / drugs policy", "https://www.government.nl/topics/drugs"),
        L("Dutch government — euthanasia", "https://www.government.nl/topics/euthanasia"),
    ],
    "jur-be": [
        L("FAMHP — Federal Agency for Medicines", "https://www.famhp.be"),
        L("Belgian euthanasia law information (FPS Health)", "https://www.health.belgium.be"),
    ],
    "jur-ch": [
        L("Swissmedic", "https://www.swissmedic.ch"),
        L("BAG — Federal Office of Public Health", "https://www.bag.admin.ch"),
        L("Swiss Criminal Code (Fedlex)", "https://www.fedlex.admin.ch"),
    ],
    "jur-au": [
        L("TGA — Therapeutic Goods Administration", "https://www.tga.gov.au"),
        L("TGA — Psilocybin and MDMA rescheduling", "https://www.tga.gov.au/news/media-releases/change-classification-psilocybin-and-mdma-enable-prescribing-authorised-psychiatrists"),
        L("Poisons Standard (SUSMP)", "https://www.tga.gov.au/resources/publication/scheduling-medicines-poisons"),
    ],
    "jur-ca": [
        L("Health Canada — Drugs & health products", "https://www.canada.ca/en/health-canada/services/drugs-health-products.html"),
        L("Controlled Drugs and Substances Act", "https://laws-lois.justice.gc.ca/eng/acts/c-38.8/"),
        L("Health Canada — Medical assistance in dying", "https://www.canada.ca/en/health-canada/services/medical-assistance-dying.html"),
        L("Special Access Programme", "https://www.canada.ca/en/health-canada/services/drugs-health-products/special-access-programme-drugs.html"),
        L("Cannabis Act overview", "https://www.canada.ca/en/health-canada/services/drugs-medication/cannabis.html"),
    ],
    "jur-mx": [
        L("COFEPRIS", "https://www.gob.mx/cofepris"),
        L("Ley General de Salud (Diputados)", "https://www.diputados.gob.mx/LeyesBiblio/pdf/LGS.pdf"),
    ],
    "jur-br": [
        L("ANVISA", "https://www.gov.br/anvisa/pt-br"),
        L("Brazil government — health regulations", "https://www.gov.br/saude"),
    ],
    "jur-jp": [
        L("PMDA — Pharmaceuticals and Medical Devices Agency", "https://www.pmda.go.jp/english/"),
        L("MHLW — Ministry of Health, Labour and Welfare", "https://www.mhlw.go.jp/english/"),
    ],
    "jur-kr": [
        L("MFDS — Ministry of Food and Drug Safety", "https://www.mfds.go.kr/eng/index.do"),
    ],
    "jur-sg": [
        L("HSA — Health Sciences Authority", "https://www.hsa.gov.sg"),
        L("CNB — Central Narcotics Bureau", "https://www.cnb.gov.sg"),
    ],
    "jur-in": [
        L("CDSCO — Central Drugs Standard Control Organization", "https://cdsco.gov.in"),
        L("NDPS Act overview (India Code)", "https://www.indiacode.nic.in"),
    ],
    "jur-il": [
        L("Israel Ministry of Health", "https://www.gov.il/en/departments/ministry_of_health"),
    ],
    "jur-uae": [
        L("UAE Ministry of Health and Prevention", "https://mohap.gov.ae"),
        L("Dubai Health Authority", "https://www.dha.gov.ae"),
    ],
    "jur-th": [
        L("Thai FDA", "https://www.fda.moph.go.th"),
    ],
    "jur-tu": [
        L("TİTCK — Turkish Medicines and Medical Devices Agency", "https://www.titck.gov.tr"),
    ],
    "jur-se": [
        L("Läkemedelsverket — Swedish Medical Products Agency", "https://www.lakemedelsverket.se/en"),
    ],
    "jur-po": [
        L("URPL — Polish Office for Registration of Medicinal Products", "https://www.urpl.gov.pl"),
    ],
    "jur-pt": [
        L("INFARMED", "https://www.infarmed.pt"),
        L("SICAD — addictive behaviours", "https://www.sicad.pt"),
    ],
    "jur-jm": [
        L("Ministry of Health Jamaica", "https://www.moh.gov.jm"),
    ],
    "jur-za": [
        L("SAHPRA", "https://www.sahpra.org.za"),
    ],
    "jur-ar": [
        L("ANMAT", "https://www.argentina.gob.ar/anmat"),
    ],
    "jur-cl": [
        L("ISP Chile — Instituto de Salud Pública", "https://www.ispch.cl"),
    ],
    "jur-cr": [
        L("Ministerio de Salud Costa Rica", "https://www.ministeriodesalud.go.cr"),
    ],
    "jur-ph": [
        L("FDA Philippines", "https://www.fda.gov.ph"),
    ],
    "jur-gr": [
        L("EOF — Greek National Organization for Medicines", "https://www.eof.gr"),
    ],
    "jur-hn-prospera": [
        L("Próspera ZEDE", "https://prospera.hn"),
    ],
}

# Pair-specific regulation / programme links (override or prepend)
PAIR_LINKS = {
    ("proc-psilocybin-trd", "jur-us-or"): [
        L("Oregon Psilocybin Services Act / OPS programme", "https://www.oregon.gov/oha/PH/PREVENTIONWELLNESS/Pages/Psilocybin-Services.aspx", "ORS 475A"),
        L("OPS administrative rules", "https://secure.sos.state.or.us/oard/displayDivisionRules.action?selectedDivision=4140"),
    ],
    ("proc-psilocybin-eol", "jur-us-or"): [
        L("Oregon Psilocybin Services", "https://www.oregon.gov/oha/PH/PREVENTIONWELLNESS/Pages/Psilocybin-Services.aspx", "ORS 475A"),
    ],
    ("proc-psilocybin-trd", "jur-au"): [
        L("TGA — psilocybin/MDMA classification change", "https://www.tga.gov.au/news/media-releases/change-classification-psilocybin-and-mdma-enable-prescribing-authorised-psychiatrists"),
        L("TGA Special Access / Authorised Prescriber", "https://www.tga.gov.au/products/unapproved-therapeutic-goods/special-access-scheme-and-authorised-prescribers"),
    ],
    ("proc-mdma-ptsd", "jur-au"): [
        L("TGA — MDMA authorised psychiatrist pathway", "https://www.tga.gov.au/news/media-releases/change-classification-psilocybin-and-mdma-enable-prescribing-authorised-psychiatrists"),
    ],
    ("proc-psilocybin-trd", "jur-ca"): [
        L("Health Canada Special Access Programme", "https://www.canada.ca/en/health-canada/services/drugs-health-products/special-access-programme-drugs.html"),
        L("CDSA", "https://laws-lois.justice.gc.ca/eng/acts/c-38.8/"),
    ],
    ("proc-lsd-anxiety", "jur-ch"): [
        L("BAG — Federal Office of Public Health", "https://www.bag.admin.ch"),
        L("Swissmedic", "https://www.swissmedic.ch"),
    ],
    ("proc-maid", "jur-ca"): [
        L("Health Canada — MAID", "https://www.canada.ca/en/health-canada/services/medical-assistance-dying.html"),
        L("Bill C-7 (MAID expansion)", "https://www.parl.ca/DocumentViewer/en/43-2/bill/C-7/royal-assent"),
    ],
    ("proc-maid", "jur-ch"): [
        L("Swiss Criminal Code Art. 115 context (Fedlex)", "https://www.fedlex.admin.ch"),
        L("Dignitas — legal basis overview", "https://www.dignitas.ch"),
    ],
    ("proc-maid", "jur-nl"): [
        L("Dutch government — euthanasia", "https://www.government.nl/topics/euthanasia"),
    ],
    ("proc-maid", "jur-be"): [
        L("Belgian FPS Health — euthanasia", "https://www.health.belgium.be"),
    ],
    ("proc-maid", "jur-es"): [
        L("Organic Law 3/2021 (euthanasia) — BOE", "https://www.boe.es/buscar/act.php?id=BOE-A-2021-4628"),
    ],
    ("proc-ketamine-depression", "jur-us-federal"): [
        L("Spravato (esketamine) REMS / FDA label info", "https://www.fda.gov/drugs"),
        L("DEA Schedule III (ketamine)", "https://www.dea.gov/drug-information/drug-scheduling"),
    ],
    ("proc-stem-car-t", "jur-us-federal"): [
        L("FDA — approved cellular & gene therapy products", "https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products/approved-cellular-and-gene-therapy-products"),
    ],
    ("proc-gene-crispr", "jur-us-federal"): [
        L("FDA — Casgevy / gene therapy announcements", "https://www.fda.gov/news-events/press-announcements/fda-approves-first-gene-therapies-treat-patients-sickle-cell-disease"),
        L("FDA Right to Try", "https://www.fda.gov/patients/learn-about-expanded-access-and-other-treatment-options/right-try"),
    ],
    ("proc-gene-aa9", "jur-us-federal"): [
        L("FDA — Zolgensma", "https://www.fda.gov/vaccines-blood-biologics/zolgensma"),
    ],
    ("proc-gene-aa9", "jur-de"): [
        L("EMA — Zolgensma EPAR", "https://www.ema.europa.eu/en/medicines/human/EPAR/zolgensma"),
        L("BfArM", "https://www.bfarm.de"),
    ],
    ("proc-mito-replacement", "jur-uk"): [
        L("HFEA — mitochondrial donation", "https://www.hfea.gov.uk"),
        L("HFEA — mitochondrial donation treatment", "https://www.hfea.gov.uk/treatments/embryo-testing-and-treatments-for-disease/mitochondrial-donation-treatment/"),
    ],
    ("proc-mito-replacement", "jur-us-federal"): [
        L("Congress / FDA embryo genetic modification funding restrictions (context)", "https://www.congress.gov"),
        L("FDA cellular & gene therapy", "https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products"),
    ],
    ("proc-repro-surrogacy", "jur-ca"): [
        L("Assisted Human Reproduction Act", "https://laws-lois.justice.gc.ca/eng/acts/a-13.4/"),
    ],
    ("proc-repro-surrogacy", "jur-fr"): [
        L("Code civil Art. 16-7 (Légifrance)", "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006419302"),
    ],
    ("proc-repro-surrogacy", "jur-de"): [
        L("Embryonenschutzgesetz (ESchG)", "https://www.gesetze-im-internet.de/eschg/"),
    ],
    ("proc-repro-surrogacy", "jur-es"): [
        L("Ley 14/2006 técnicas de reproducción humana asistida (BOE)", "https://www.boe.es/buscar/act.php?id=BOE-A-2006-9292"),
    ],
    ("proc-medical-cannabis", "jur-ca"): [
        L("Cannabis Act / medical cannabis", "https://www.canada.ca/en/health-canada/services/drugs-medication/cannabis.html"),
    ],
    ("proc-medical-cannabis", "jur-de"): [
        L("BfArM — cannabis as medicine", "https://www.bfarm.de"),
        L("CanG / cannabis reforms context", "https://www.bundesgesundheitsministerium.de"),
    ],
    ("proc-medical-cannabis", "jur-uk"): [
        L("MHRA / NHS — cannabis-based products for medicinal use", "https://www.gov.uk/government/collections/medicinal-cannabis-information-and-resources"),
    ],
    ("proc-lecanemab", "jur-us-federal"): [
        L("FDA — Leqembi (lecanemab)", "https://www.fda.gov"),
        L("CMS — anti-amyloid mAb coverage context", "https://www.cms.gov"),
    ],
    ("proc-fmt", "jur-us-federal"): [
        L("FDA — FAQs about FMT", "https://www.fda.gov/vaccines-blood-biologics/guidance-documents-faqs/faqs-about-fecal-microbiota-transplantation"),
    ],
    ("proc-ozone-therapy", "jur-us-federal"): [
        L("FDA — ozone generators / medical claims", "https://www.fda.gov/consumers/consumer-updates"),
    ],
    ("proc-peptide-bpc", "jur-us-federal"): [
        L("FDA — bulk substances that may present significant safety risks", "https://www.fda.gov/drugs/human-drug-compounding/certain-bulk-drug-substances-use-compounding-may-present-significant-safety-risks"),
    ],
    ("proc-tms-depression", "jur-us-federal"): [
        L("FDA device clearances (search TMS)", "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm"),
    ],
    ("proc-hbot", "jur-us-federal"): [
        L("UHMS / hyperbaric medicine resources", "https://www.uhms.org"),
        L("FDA radiation-emitting products — hyperbaric", "https://www.fda.gov/radiation-emitting-products"),
    ],
}


def _dedupe_links(links):
    seen = set()
    out = []
    for link in links:
        if not link or not link.get("url"):
            continue
        url = link["url"].strip()
        if url in seen:
            continue
        seen.add(url)
        out.append(link)
    return out


def links_for_pair(procedure_id: str, jurisdiction_id: str, existing_sources=None) -> list:
    """Build best-effort regulation link list for one access cell."""
    links = []

    # 1) Pair-specific
    links.extend(PAIR_LINKS.get((procedure_id, jurisdiction_id), []))

    # 2) Psychedelic law sources from prohibition matrix
    law = JUR_PSYCHEDELIC_LAW.get(jurisdiction_id)
    if law and law.get("sources"):
        for s in law["sources"]:
            if s.get("url"):
                links.append(L(s.get("title") or "Regulatory source", s["url"]))

    # 3) Jurisdiction regulation profile statutes with URLs
    reg = all_jurisdiction_regulation().get(jurisdiction_id) or {}
    for s in reg.get("key_statutes") or []:
        if s.get("url"):
            links.append(L(s.get("name") or "Statute", s["url"], s.get("citation")))

    # 4) Default jurisdiction portals
    links.extend(JUR_DEFAULT_LINKS.get(jurisdiction_id, []))

    # 5) Existing row sources
    for s in existing_sources or []:
        if isinstance(s, dict) and s.get("url"):
            links.append(L(s.get("title") or "Source", s["url"]))

    return _dedupe_links(links)


def apply_regulation_links_to_record(ar_orm) -> bool:
    """Set ar.regulation_links JSON if empty or upgrade from sources. Returns True if changed."""
    import json
    existing = []
    if ar_orm.regulation_links:
        try:
            existing = json.loads(ar_orm.regulation_links)
        except Exception:
            existing = []
    sources = []
    if ar_orm.sources:
        try:
            sources = json.loads(ar_orm.sources)
        except Exception:
            sources = []
    new_links = links_for_pair(ar_orm.procedure_id, ar_orm.jurisdiction_id, sources)
    # Prefer richer new list if existing empty or shorter
    if not new_links:
        return False
    if existing and len(existing) >= len(new_links):
        # still refresh if existing has no urls
        if all(x.get("url") for x in existing):
            return False
    new_json = json.dumps(new_links)
    if ar_orm.regulation_links != new_json:
        ar_orm.regulation_links = new_json
        return True
    return False
