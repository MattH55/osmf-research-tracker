"""Infer access cells where no explicit policy row exists.

Uses:
  - Jurisdiction regulation profile (psychedelic/cannabis/MAID defaults, RTT, compounding)
  - Parent jurisdiction profile (e.g. US states ← federal)
  - Therapy class (modality, schedule, global posture, id patterns)

Does NOT overwrite existing AccessRecords. Labels every row as inferred with
confidence High only when the jurisdiction profile default is an exact class match
(e.g. psychedelic × psychedelic_default=Prohibited); otherwise Moderate/Low.

Informational only — not legal advice.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from .models import (
    LegalStatus as LS,
    AccessPathway as AP,
    OversightQuality as OQ,
    PriceConfidence as PC,
    Confidence as CF,
    Volatility as VL,
)
from .seed_prohibitions import (
    CONTROLLED_PSYCHEDELICS,
    all_jurisdiction_regulation,
    all_therapy_control_meta,
)
from .seed_practitioner_setup import merged_setup

LV = date(2026, 7, 17)
INFERENCE_BY = "regulatory_inference_v1"

# ── Therapy family classification ───────────────────────────────────────────

PSYCHEDELIC_SET = set(CONTROLLED_PSYCHEDELICS)

KETAMINE_SET = {
    "proc-ketamine-depression",
    "proc-ketamine-assisted-psychotherapy",
}

# Commercial advanced therapies often authorized in ICH-class markets
COMMERCIAL_CELL_GENE = {
    "proc-stem-car-t",
    "proc-gene-crispr",
    "proc-gene-aa9",
    "proc-til-melanoma",
}

EXPERIMENTAL_CELL_GENE = {
    "proc-car-t-solid",
    "proc-stem-msc",
    "proc-stem-exosome",
    "proc-stem-nsc",
    "proc-cord-blood",
    "proc-dendritic-vaccine",
    "proc-photoimmunotherapy",
    "proc-apheresis-longcovid",
}

UNAPPROVED_PEPTIDES = {
    "proc-peptide-bpc",
    "proc-peptide-cjc-ipa",
    "proc-peptide-ss31",
    "proc-peptide-thymosin",
}

LABELED_PEPTIDES = {
    "proc-peptide-tesamorelin",
    "proc-pt-141",
}

# Off-label / repurposed small molecules typically prescribe-able where MD practice exists
OFFLABEL_RX = {
    "proc-repurposed-semaglutide",
    "proc-glp1-addiction",
    "proc-repurposed-rapamycin",
    "proc-metformin-longevity",
    "proc-repurposed-ldn",
    "proc-repurposed-methylene",
    "proc-sglt2-hf",
    "proc-prazosin-ptsd",
    "proc-baclofen-aud",
    "proc-trt",
    "proc-low-dose-lithium",
    "proc-senolytics",
    "proc-chelation",
    "proc-ivig",
    "proc-lecanemab",
    "proc-fecal-sibo",
}

DEVICE_NEURO = {
    "proc-tms-depression",
    "proc-tms-ocd",
    "proc-dbs-parkinson",
    "proc-vns-depression",
    "proc-fus-tremor",
    "proc-pef-ablation",
}

DEVICE_OTHER = {
    "proc-hbot",
    "proc-cryotherapy",
    "proc-ecmo-bridge",
    "proc-proton-therapy",
}

REPRO = {
    "proc-repro-ivf",
    "proc-egg-freezing",
    "proc-repro-surrogacy",
    "proc-uterine-transplant",
    "proc-mito-replacement",
}

WELLNESS_CASH = {
    "proc-nad-iv",
    "proc-nmn-nmad",
    "proc-prp-therapy",
}

FMT_SET = {"proc-fmt"}
OZONE_SET = {"proc-ozone-therapy"}
CANNABIS_SET = {"proc-medical-cannabis"}
MAID_SET = {"proc-maid"}

# Jurisdictions with mature medicines regulators (for commercial ATMP inference)
ICH_LIKE_REGULATORS = {
    "FDA", "EMA", "TGA", "PMDA", "Health Canada", "MHRA", "Swissmedic",
    "BfArM", "ANSM", "AEMPS", "MEB", "FAMHP", "HSA", "MFDS", "Medsafe",
}


def therapy_family(proc_id: str, modality: str = "", posture: str = "") -> str:
    if proc_id in PSYCHEDELIC_SET:
        return "psychedelic"
    if proc_id in CANNABIS_SET:
        return "cannabis"
    if proc_id in MAID_SET:
        return "maid"
    if proc_id in KETAMINE_SET:
        return "ketamine"
    if proc_id in COMMERCIAL_CELL_GENE:
        return "cell_gene_commercial"
    if proc_id in EXPERIMENTAL_CELL_GENE:
        return "cell_gene_experimental"
    if proc_id in UNAPPROVED_PEPTIDES:
        return "peptide_unapproved"
    if proc_id in LABELED_PEPTIDES:
        return "peptide_labeled"
    if proc_id in OFFLABEL_RX:
        return "offlabel_rx"
    if proc_id in DEVICE_NEURO or proc_id in DEVICE_OTHER:
        return "device"
    if proc_id in REPRO:
        return "reproductive"
    if proc_id in WELLNESS_CASH:
        return "wellness_cash"
    if proc_id in FMT_SET:
        return "fmt"
    if proc_id in OZONE_SET:
        return "ozone"
    # Fallback by modality string
    m = (modality or "").lower()
    if "controlled" in m or "psychedelic" in m:
        return "psychedelic"
    if "gene" in m or "cell" in m or "stem" in m:
        return "cell_gene_experimental"
    if "peptide" in m:
        return "peptide_unapproved"
    if "reproduct" in m:
        return "reproductive"
    if "dying" in m or "maid" in m:
        return "maid"
    return "general_medical"


def _reg_maps() -> dict:
    return all_jurisdiction_regulation()


def resolve_reg_profile(jur_id: str, parent_id: Optional[str], jur_reg_json: Optional[dict]) -> dict:
    """Merge DB regulation_json, static profiles, and parent defaults."""
    static = _reg_maps()
    base: dict[str, Any] = {}
    # Parent first (inheritance), then static self, then live DB JSON wins
    if parent_id:
        base.update(static.get(parent_id) or {})
        # don't inherit pending legislation blindly from parent as "this jur's" pending
    base.update(static.get(jur_id) or {})
    if jur_reg_json:
        base.update({k: v for k, v in jur_reg_json.items() if v is not None})
    return base


def _cell(
    proc_id: str,
    jur_id: str,
    *,
    legal_status,
    pathway,
    authority: str,
    legal_basis: str,
    details: str,
    summary: str,
    eligibility: str,
    provider: str,
    oversight=OQ.MEDIUM,
    confidence=CF.LOW,
    volatility=VL.STABLE,
    risk: str = "",
    residency: str = "",
    cost: str = "Not priced — inferred cell",
):
    setup = merged_setup(proc_id, jur_id) or merged_setup(proc_id)
    sources = [{
        "title": "Inferred from jurisdiction regulatory profile + therapy class",
        "url": None,
        "note": "Not an explicit statute-by-statute determination for this pair",
    }]
    return {
        "procedure_id": proc_id,
        "jurisdiction_id": jur_id,
        "legal_status": legal_status,
        "access_pathway": pathway,
        "oversight_quality": oversight,
        "regulatory_authority": authority,
        "legal_basis": legal_basis,
        "access_pathway_details": details,
        "eligibility_requirements": eligibility,
        "provider_requirements": provider,
        "oversight_notes": (
            "INFERRED cell — no explicit curated AccessCell existed for this pair. "
            "Derived from jurisdiction defaults (psychedelic/cannabis/MAID/RTT/compounding) "
            "and therapy class rules. Confirm primary law before relying."
        ),
        "estimated_cost_range_usd": cost,
        "cost_notes": "No market price research for this inferred cell.",
        "residency_travel_notes": residency or "Residency rules not specifically researched for this inferred cell.",
        "risk_notes": risk or "Inference risk: actual law may be stricter or more permissive than defaults.",
        "arbitrage_summary": summary,
        "price_usd": None,
        "price_basis": "cash_pay",
        "price_confidence": PC.UNKNOWN,
        "total_access_cost_usd": None,
        "confidence": confidence,
        "volatility": volatility,
        "verified_by": INFERENCE_BY,
        "last_verified": LV,
        "sources": sources,
        "regulation_links": [],
        "setup_requirements": setup,
        "known_risk_flags": json.dumps(["inferred_policy"]),
    }


def _authority(reg: dict) -> str:
    return reg.get("drug_regulator") or reg.get("health_authority") or "National medicines / health authority (inferred)"


def _compounding_permissive(reg: dict) -> bool:
    env = (reg.get("compounding_environment") or "").lower()
    if not env:
        return False
    if any(x in env for x in ("restrict", "ban", "prohib", "limited", "hostile")):
        return False
    if any(x in env for x in ("permiss", "active", "503a", "503b", "widespread", "common")):
        return True
    return "compound" in env


def _has_rtt(reg: dict) -> bool:
    return bool(reg.get("right_to_try_or_expanded_access"))


def _ich_like(reg: dict) -> bool:
    auth = f"{reg.get('drug_regulator') or ''} {reg.get('health_authority') or ''}"
    return any(x in auth for x in ICH_LIKE_REGULATORS)


def infer_for_pair(
    proc_id: str,
    jur_id: str,
    *,
    modality: str = "",
    posture: str = "",
    parent_id: Optional[str] = None,
    jur_reg_json: Optional[dict] = None,
    proc_name: str = "",
) -> Optional[dict]:
    """Return an access-record dict or None if we refuse to invent a posture."""
    family = therapy_family(proc_id, modality, posture)
    reg = resolve_reg_profile(jur_id, parent_id, jur_reg_json)
    auth = _authority(reg)
    name = proc_name or proc_id

    # ── Psychedelics ← psychedelic_default ────────────────────────────────
    if family == "psychedelic":
        d = reg.get("psychedelic_default")
        if not d:
            # UN-convention-style conservative default for sovereigns without profile
            d = "Prohibited"
            conf = CF.LOW
            basis_extra = "No jurisdiction psychedelic_default on file — applied conservative Schedule-I-class default."
        else:
            conf = CF.MODERATE if d == "Prohibited" else CF.MODERATE
            basis_extra = f"Jurisdiction psychedelic_default={d}."
        basis = f"Inferred: {basis_extra}"
        if d == "Prohibited":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PROHIBITED, pathway=AP.NONE,
                authority=auth, legal_basis=basis,
                details=f"Classical/atypical psychedelic therapy for {name} treated as prohibited outside narrow research under default national posture.",
                summary="Inferred prohibited under jurisdiction psychedelic default / UN-style scheduling. Not a lawful commercial therapy market.",
                eligibility="No lawful general patient pathway under inferred default.",
                provider="Cannot lawfully open a commercial program without an explicit statutory exception.",
                oversight=OQ.HIGH, confidence=conf if d else CF.LOW,
                risk="Criminal liability risk if default is accurate; always verify current schedule.",
            )
        if d == "Clinical_Trial_Only":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.CLINICAL_TRIAL_ONLY, pathway=AP.CLINICAL_TRIAL_ENROLLMENT,
                authority=auth, legal_basis=basis,
                details="Default posture is trial-only; commercial service centres not inferred.",
                summary="Inferred trial-only access. Patients/providers need authorized research protocols.",
                eligibility="Trial inclusion/exclusion only.",
                provider="GCP trial site authorization; no retail clinic inference.",
                oversight=OQ.HIGH, confidence=CF.MODERATE,
            )
        if d == "Expanded_Access":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PERMITTED_EXPANDED_ACCESS, pathway=AP.EXPANDED_ACCESS,
                authority=auth, legal_basis=basis,
                details="Compassionate/special-access style default — not open retail therapy.",
                summary="Inferred special-access / expanded-access posture. High friction, case-by-case.",
                eligibility="Serious condition + access scheme criteria (verify).",
                provider="Authorized prescriber / ethics / special-access paperwork.",
                oversight=OQ.HIGH, confidence=CF.MODERATE,
            )
        if d == "Regulated_Therapy_Program":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.REGULATED_THERAPY, pathway=AP.LICENSED_PROVIDER_REGIME,
                authority=auth, legal_basis=basis,
                details="Jurisdiction signals a regulated therapy-program model for psychedelics.",
                summary="Inferred regulated program pathway may exist — still confirm license classes and product rules.",
                eligibility="Program-specific screening (age, contraindications).",
                provider="Program licenses / facilitator or medical credentials per local scheme.",
                oversight=OQ.REGULATED_HIGH, confidence=CF.MODERATE,
            )
        if d == "Decriminalized_No_Supply":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.DECRIMINALIZED_NO_SUPPLY, pathway=AP.NONE,
                authority=auth, legal_basis=basis,
                details="Personal use may be decriminalized; commercial therapy supply not inferred as lawful.",
                summary="Inferred decrim-without-supply. Not a clinic destination under default rules.",
                eligibility="No licensed therapy supply inferred.",
                provider="No commercial pathway inferred.",
                oversight=OQ.VARIABLE, confidence=CF.MODERATE,
            )
        if d == "Unregulated_Permitted":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.UNREGULATED_PERMITTED, pathway=AP.MEDICAL_TOURISM_CASH,
                authority=auth, legal_basis=basis,
                details="Default allows relatively open practice — quality and consumer protection still apply.",
                summary="Inferred permissive/unregulated posture — high variance in quality; diligence essential.",
                eligibility="Operator-defined; local consumer law applies.",
                provider="Local business/medical rules may still apply even if substance posture is open.",
                oversight=OQ.MINIMAL, confidence=CF.LOW,
                volatility=VL.ACTIVE_FLUX,
            )
        # Highly_Variable or unknown enum
        return _cell(
            proc_id, jur_id,
            legal_status=LS.UNKNOWN, pathway=AP.NONE,
            authority=auth, legal_basis=basis + " Posture highly variable — no single inference safe.",
            details="Do not assume commercial legality. Research subnational and product-specific rules.",
            summary="Inferred unknown/variable psychedelic posture — explicit research required.",
            eligibility="Unknown.",
            provider="Unknown — obtain counsel.",
            oversight=OQ.VARIABLE, confidence=CF.LOW,
            volatility=VL.ACTIVE_FLUX,
        )

    # ── Cannabis ← cannabis_default ───────────────────────────────────────
    if family == "cannabis":
        d = reg.get("cannabis_default") or "Prohibited"
        conf = CF.MODERATE if reg.get("cannabis_default") else CF.LOW
        basis = f"Inferred from cannabis_default={d}" + ("" if reg.get("cannabis_default") else " (defaulted; no profile field).")
        if d == "Prohibited":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PROHIBITED, pathway=AP.NONE,
                authority=auth, legal_basis=basis,
                details="Medical cannabis programme not inferred under prohibited default.",
                summary="Inferred: no lawful medical cannabis market under jurisdiction default.",
                eligibility="No pathway.", provider="No pathway.",
                oversight=OQ.HIGH, confidence=conf,
            )
        if d == "Medical_Only":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.REGULATED_THERAPY, pathway=AP.STANDARD_PRESCRIPTION,
                authority=auth, legal_basis=basis,
                details="Medical-only default: prescription/authorization + licensed supply chain typically required.",
                summary="Inferred medical-only cannabis pathway (prescription/authorization model).",
                eligibility="Qualifying medical indication under national programme (verify list).",
                provider="Authorized prescriber + licensed pharmacy/dispensary channel.",
                oversight=OQ.REGULATED_MODERATE, confidence=conf,
            )
        if d == "Medical_And_Adult_Use":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.REGULATED_THERAPY, pathway=AP.LICENSED_PROVIDER_REGIME,
                authority=auth, legal_basis=basis,
                details="Medical and adult-use both signalled — medical channel still distinct for clinical practice.",
                summary="Inferred multi-channel cannabis market; medical practice still needs programme compliance.",
                eligibility="Medical programme or adult-use age rules depending on channel.",
                provider="Recommend-only vs retail licenses are different tracks.",
                oversight=OQ.REGULATED_MODERATE, confidence=conf,
            )
        if d == "Decriminalized":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.DECRIMINALIZED, pathway=AP.NONE,
                authority=auth, legal_basis=basis,
                details="Decrim does not automatically create medical supply or clinic licensing.",
                summary="Inferred decriminalized personal use — medical supply still may be restricted.",
                eligibility="Not a full medical programme inference.",
                provider="Verify medical licensing separately.",
                oversight=OQ.VARIABLE, confidence=CF.LOW,
            )
        return _cell(
            proc_id, jur_id,
            legal_status=LS.UNKNOWN, pathway=AP.NONE,
            authority=auth, legal_basis=basis,
            details="Cannabis rules highly variable; no safe single pathway inference.",
            summary="Inferred variable cannabis posture — research required.",
            eligibility="Unknown.", provider="Unknown.",
            oversight=OQ.VARIABLE, confidence=CF.LOW, volatility=VL.ACTIVE_FLUX,
        )

    # ── MAID ← assisted_dying_default ─────────────────────────────────────
    if family == "maid":
        d = reg.get("assisted_dying_default") or "Prohibited"
        conf = CF.MODERATE if reg.get("assisted_dying_default") else CF.LOW
        basis = f"Inferred from assisted_dying_default={d}"
        vol = VL.PENDING_LEGISLATION if d == "Pending_Legislation" else VL.STABLE
        if d in ("Prohibited", "Pending_Legislation"):
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PROHIBITED, pathway=AP.NONE,
                authority=auth, legal_basis=basis,
                details="No open MAID pathway under jurisdiction default (pending bills may change this).",
                summary="Inferred: MAID not available under current default posture.",
                eligibility="No pathway.", provider="No pathway.",
                oversight=OQ.HIGH, confidence=conf, volatility=vol,
            )
        if d == "Limited_Subnational":
            # Federal / national id: not generally available; states may differ
            if parent_id is None and "us" in jur_id:
                return _cell(
                    proc_id, jur_id,
                    legal_status=LS.PROHIBITED, pathway=AP.NONE,
                    authority=auth, legal_basis=basis + " (national/federal cell).",
                    details="Assisted dying is subnational only — this national/federal cell has no general pathway.",
                    summary="Inferred: no federal/national MAID programme; check authorized states/provinces separately.",
                    eligibility="Not at this jurisdiction level.",
                    provider="Not at this jurisdiction level.",
                    oversight=OQ.HIGH, confidence=CF.MODERATE,
                )
            return _cell(
                proc_id, jur_id,
                legal_status=LS.UNKNOWN, pathway=AP.NONE,
                authority=auth, legal_basis=basis,
                details="Limited subnational MAID elsewhere in the country — this unit may or may not participate.",
                summary="Inferred unclear at this subnational unit — verify local statute.",
                eligibility="Verify local eligibility statute.",
                provider="Verify local provider authorization.",
                oversight=OQ.VARIABLE, confidence=CF.LOW,
            )
        if d in ("Assisted_Suicide_Only", "Euthanasia_And_Assisted_Suicide"):
            return _cell(
                proc_id, jur_id,
                legal_status=LS.REGULATED_THERAPY, pathway=AP.LICENSED_PROVIDER_REGIME,
                authority=auth, legal_basis=basis,
                details=f"Default signals regulated assisted dying ({d}). Safeguards, waiting periods, and reporting are typically mandatory.",
                summary="Inferred regulated MAID pathway may exist — confirm track rules and provider duties.",
                eligibility="Capacity, voluntariness, medical criteria per national/provincial law.",
                provider="Authorized assessors/providers; mandatory reporting.",
                oversight=OQ.REGULATED_HIGH, confidence=conf,
            )
        return _cell(
            proc_id, jur_id,
            legal_status=LS.UNKNOWN, pathway=AP.NONE,
            authority=auth, legal_basis=basis,
            details="MAID posture not safely inferable.",
            summary="Inferred unknown MAID posture.",
            eligibility="Unknown.", provider="Unknown.",
            oversight=OQ.VARIABLE, confidence=CF.LOW,
        )

    # ── Ketamine (scheduled but medical) ──────────────────────────────────
    if family == "ketamine":
        return _cell(
            proc_id, jur_id,
            legal_status=LS.APPROVED_OFF_LABEL, pathway=AP.OFF_LABEL_PRESCRIPTION,
            authority=auth,
            legal_basis=(
                f"Inferred: ketamine is a scheduled medicine with accepted anesthetic use in most systems "
                f"({reg.get('controlled_substance_framework') or 'national scheduling'}). "
                "Depression/KAP use is typically off-label clinic practice where medical licensing allows."
            ),
            details=(
                "Inferred off-label / clinic model under medical and controlled-substance rules. "
                "Esketamine (Spravato) may have separate REMS/label pathway where marketed — not assumed here."
            ),
            summary="Inferred: medical controlled-substance clinic pathway likely if medical practice is lawful; still confirm scheduling and clinic rules.",
            eligibility="Medical evaluation; controlled-substance prescribing standards.",
            provider="Licensed prescriber + controlled-substance authority; monitoring protocols.",
            oversight=OQ.REGULATED_MODERATE,
            confidence=CF.MODERATE if _ich_like(reg) or reg else CF.LOW,
            risk="Diversion controls, monitoring, and off-label consent still apply.",
        )

    # ── Commercial cell/gene ──────────────────────────────────────────────
    if family == "cell_gene_commercial":
        if _ich_like(reg) or reg.get("drug_regulator"):
            return _cell(
                proc_id, jur_id,
                legal_status=LS.FULLY_APPROVED, pathway=AP.STANDARD_PRESCRIPTION,
                authority=auth,
                legal_basis="Inferred: commercial ATMP/gene-therapy products are typically authorized only via national regulator + designated centres in ICH-class systems.",
                details="Inferred hospital/centre-only delivery. Product-specific authorization and REMS/centre networks usually required.",
                summary="Inferred: authorized treatment-centre pathway in regulated markets — not outpatient startup.",
                eligibility="Labeled indication + centre eligibility.",
                provider="Manufacturer-authorized / FACT-class centre; hospital privileges.",
                oversight=OQ.REGULATED_HIGH,
                confidence=CF.MODERATE if _ich_like(reg) else CF.LOW,
                cost="Very high — product + inpatient (not estimated here)",
            )
        if _has_rtt(reg):
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PERMITTED_EXPANDED_ACCESS, pathway=AP.EXPANDED_ACCESS,
                authority=auth,
                legal_basis="Inferred: no clear commercial ATMP authorization assumed; expanded-access/RTT flag present.",
                details="Experimental / special access until local marketing authorization exists.",
                summary="Inferred special-access / trial-adjacent pathway only.",
                eligibility="Serious/life-threatening criteria under local scheme.",
                provider="Authorized investigational site.",
                oversight=OQ.HIGH, confidence=CF.LOW,
            )
        return _cell(
            proc_id, jur_id,
            legal_status=LS.CLINICAL_TRIAL_ONLY, pathway=AP.CLINICAL_TRIAL_ENROLLMENT,
            authority=auth,
            legal_basis="Inferred: advanced cell/gene therapy without clear commercial authorization → trial-only default.",
            details="No open commercial centre pathway inferred.",
            summary="Inferred trial-only for advanced cell/gene therapy.",
            eligibility="Trial criteria.", provider="Trial site.",
            oversight=OQ.HIGH, confidence=CF.LOW,
        )

    # ── Experimental cell/gene / MSC / exosome ────────────────────────────
    if family == "cell_gene_experimental":
        status = LS.CLINICAL_TRIAL_ONLY
        path = AP.CLINICAL_TRIAL_ENROLLMENT
        if _has_rtt(reg):
            status = LS.PERMITTED_EXPANDED_ACCESS
            path = AP.EXPANDED_ACCESS
        # Unproven MSC/exosome clinics often gray/prohibited for marketing claims
        if proc_id in ("proc-stem-msc", "proc-stem-exosome", "proc-stem-nsc"):
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PHYSICIAN_DISCRETION_GRAY if not _ich_like(reg) else LS.CLINICAL_TRIAL_ONLY,
                pathway=AP.MEDICAL_TOURISM_CASH if not _ich_like(reg) else AP.CLINICAL_TRIAL_ENROLLMENT,
                authority=auth,
                legal_basis="Inferred: unproven regenerative marketing is often enforcement-priority in strict regulators; gray abroad.",
                details="Homologous use / minimal manipulation exceptions are narrow. Commercial 'stem cell tourism' frequently unlawful for disease claims in ICH markets.",
                summary="Inferred high regulatory risk for commercial unproven cell therapy — trial or foreign gray market only.",
                eligibility="If any, under trial/expanded access — not wellness claims.",
                provider="Legitimate path is trial/IND-class; cash clinics often non-compliant.",
                oversight=OQ.VARIABLE, confidence=CF.LOW, volatility=VL.ACTIVE_FLUX,
                risk="Enforcement actions common for disease claims without approval.",
            )
        return _cell(
            proc_id, jur_id,
            legal_status=status, pathway=path,
            authority=auth,
            legal_basis="Inferred: experimental advanced therapy → trial/expanded access default.",
            details="No open commercial programme inferred.",
            summary="Inferred trial/special-access only for experimental cell/gene modality.",
            eligibility="Protocol criteria.", provider="Authorized research site.",
            oversight=OQ.HIGH, confidence=CF.LOW,
        )

    # ── Unapproved peptides ───────────────────────────────────────────────
    if family == "peptide_unapproved":
        if _compounding_permissive(reg) and not _ich_like(reg):
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PHYSICIAN_DISCRETION_GRAY, pathway=AP.COMPOUNDING,
                authority=auth,
                legal_basis="Inferred: unapproved peptide + relatively open compounding climate → gray compounding risk.",
                details="Still may violate advertising/medicine laws. Bulk substance status is critical.",
                summary="Inferred gray compounding climate — high legal risk even if local practice is common.",
                eligibility="Medical justification documentation if any.",
                provider="Prescriber + compounder compliance uncertain.",
                oversight=OQ.MINIMAL, confidence=CF.LOW, volatility=VL.ACTIVE_FLUX,
            )
        return _cell(
            proc_id, jur_id,
            legal_status=LS.PROHIBITED, pathway=AP.NONE,
            authority=auth,
            legal_basis="Inferred: unapproved peptide products generally cannot be marketed as medicines; compounding often restricted (esp. ICH markets).",
            details="FDA Category 2 / similar concerns in peer regulators. No lawful routine clinic pathway inferred.",
            summary="Inferred: no lawful routine commercial pathway for unapproved research peptides.",
            eligibility="None for commercial therapy claims.",
            provider="Cannot lawfully scale a clinic on unapproved bulk peptides under typical rules.",
            oversight=OQ.HIGH, confidence=CF.MODERATE if _ich_like(reg) else CF.LOW,
        )

    # ── Labeled peptides ──────────────────────────────────────────────────
    if family == "peptide_labeled":
        return _cell(
            proc_id, jur_id,
            legal_status=LS.APPROVED_ON_LABEL if _ich_like(reg) else LS.UNKNOWN,
            pathway=AP.STANDARD_PRESCRIPTION if _ich_like(reg) else AP.NONE,
            authority=auth,
            legal_basis="Inferred: products with originator labels (e.g. tesamorelin, bremelanotide) follow ordinary prescription rules where marketed.",
            details="Only where the product is actually authorized/marketed locally — registration is country-specific.",
            summary="Inferred standard Rx pathway if product is registered locally; otherwise unavailable.",
            eligibility="Labeled indication criteria.",
            provider="Prescriptive authority + specialty pharmacy as applicable.",
            oversight=OQ.REGULATED_MODERATE,
            confidence=CF.LOW,
        )

    # ── Off-label small molecules ─────────────────────────────────────────
    if family == "offlabel_rx":
        return _cell(
            proc_id, jur_id,
            legal_status=LS.APPROVED_OFF_LABEL, pathway=AP.OFF_LABEL_PRESCRIPTION,
            authority=auth,
            legal_basis="Inferred: where physicians may prescribe registered molecules, off-label use is commonly a medical-practice matter (advertising still regulated).",
            details=(
                f"Assumes a functioning medical licensing system and that the molecule class is registered for some indication. "
                f"Longevity/addiction uses may be off-label. Compounding environment: {reg.get('compounding_environment') or 'unknown'}."
            ),
            summary="Inferred off-label prescribing pathway under ordinary medical practice — confirm local formulary, controlled status, and advertising rules.",
            eligibility="Clinical judgment + informed consent for off-label use.",
            provider="Licensed prescriber; standard of care documentation.",
            oversight=OQ.REGULATED_MODERATE if _ich_like(reg) else OQ.VARIABLE,
            confidence=CF.MODERATE if _ich_like(reg) or reg.get("drug_regulator") else CF.LOW,
            risk="Payer denial common; advertising disease claims may be illegal.",
        )

    # ── Devices ───────────────────────────────────────────────────────────
    if family == "device":
        return _cell(
            proc_id, jur_id,
            legal_status=LS.FULLY_APPROVED if _ich_like(reg) else LS.PHYSICIAN_DISCRETION_GRAY,
            pathway=AP.LICENSED_PROVIDER_REGIME,
            authority=auth,
            legal_basis="Inferred: medical devices require national device registration + facility/operator rules; specialty devices are specialist-delivered.",
            details="Cleared/approved device indications vary by country. Hospital privileges often required for implantables.",
            summary="Inferred specialist/device pathway where medical device regulation exists.",
            eligibility="Indication-specific selection criteria.",
            provider="Privileged specialists + device training/proctoring.",
            oversight=OQ.REGULATED_HIGH if "dbs" in proc_id or "ecmo" in proc_id or "proton" in proc_id else OQ.REGULATED_MODERATE,
            confidence=CF.LOW,
        )

    # ── Reproductive ──────────────────────────────────────────────────────
    if family == "reproductive":
        if proc_id == "proc-mito-replacement":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.PROHIBITED, pathway=AP.NONE,
                authority=auth,
                legal_basis="Inferred: MRT is rare and usually banned outside dedicated UK-class licences; default prohibited unless explicit programme exists.",
                details="Only a handful of regimes authorize mitochondrial donation.",
                summary="Inferred prohibited/unavailable for MRT outside known licensed programmes.",
                eligibility="None under default inference.",
                provider="None under default inference.",
                oversight=OQ.HIGH, confidence=CF.MODERATE,
            )
        if proc_id == "proc-repro-surrogacy":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.UNKNOWN, pathway=AP.NONE,
                authority=auth,
                legal_basis="Inferred: surrogacy is highly jurisdiction-specific (ban vs altruistic vs commercial).",
                details="Without an explicit curated cell, do not assume surrogacy is lawful.",
                summary="Inferred unknown surrogacy posture — requires family-law research.",
                eligibility="Unknown.", provider="Unknown.",
                oversight=OQ.VARIABLE, confidence=CF.LOW, volatility=VL.ACTIVE_FLUX,
            )
        if proc_id == "proc-uterine-transplant":
            return _cell(
                proc_id, jur_id,
                legal_status=LS.CLINICAL_TRIAL_ONLY, pathway=AP.CLINICAL_TRIAL_ENROLLMENT,
                authority=auth,
                legal_basis="Inferred: uterus transplant remains experimental/limited-centre globally.",
                details="Not a standard ART service line.",
                summary="Inferred trial/limited transplant-centre only.",
                eligibility="Strict transplant criteria.", provider="Transplant programme.",
                oversight=OQ.HIGH, confidence=CF.MODERATE,
            )
        # IVF / egg freezing
        return _cell(
            proc_id, jur_id,
            legal_status=LS.FULLY_APPROVED if _ich_like(reg) or reg.get("drug_regulator") else LS.PHYSICIAN_DISCRETION_GRAY,
            pathway=AP.LICENSED_PROVIDER_REGIME,
            authority=auth,
            legal_basis="Inferred: IVF/ART is widely regulated as licensed medical practice where modern fertility care exists.",
            details="Licensing, gamete storage, and embryo rules vary; some ethics limits (e.g. donor, PGT) are jurisdiction-specific.",
            summary="Inferred licensed ART clinic pathway in regulated health systems.",
            eligibility="Clinic protocols + any national ART act limits.",
            provider="ART clinic license + lab accreditation typically required.",
            oversight=OQ.REGULATED_HIGH if _ich_like(reg) else OQ.VARIABLE,
            confidence=CF.MODERATE if _ich_like(reg) else CF.LOW,
        )

    # ── Wellness cash (NAD IV, NMN, PRP) ──────────────────────────────────
    if family == "wellness_cash":
        return _cell(
            proc_id, jur_id,
            legal_status=LS.PHYSICIAN_DISCRETION_GRAY, pathway=AP.MEDICAL_TOURISM_CASH,
            authority=auth,
            legal_basis="Inferred: wellness infusions/supplements sit in a gray zone — medical board + advertising + sterile compounding rules dominate.",
            details="Disease claims convert products into unapproved drugs. Facility/IV rules still apply.",
            summary="Inferred gray/cash wellness pathway — compliance is advertising and scope-of-practice driven.",
            eligibility="Clinic screening; not a regulated disease indication pathway.",
            provider="Medical director + IV competency where injections/infusions used.",
            oversight=OQ.MINIMAL, confidence=CF.LOW, volatility=VL.ACTIVE_FLUX,
        )

    # ── FMT ───────────────────────────────────────────────────────────────
    if family == "fmt":
        return _cell(
            proc_id, jur_id,
            legal_status=LS.APPROVED_ON_LABEL if _ich_like(reg) else LS.CLINICAL_TRIAL_ONLY,
            pathway=AP.STANDARD_PRESCRIPTION if _ich_like(reg) else AP.CLINICAL_TRIAL_ENROLLMENT,
            authority=auth,
            legal_basis="Inferred: cleared microbiota products for rCDI exist in some markets; other indications often trial-only.",
            details="Do not assume IBD/SIBO commercial FMT is authorized.",
            summary="Inferred: labeled microbiota products where registered; else trial/expanded access.",
            eligibility="Primarily recurrent C. difficile where products exist.",
            provider="GI/ID scope + product labeling.",
            oversight=OQ.REGULATED_MODERATE, confidence=CF.LOW,
        )

    # ── Ozone ─────────────────────────────────────────────────────────────
    if family == "ozone":
        return _cell(
            proc_id, jur_id,
            legal_status=LS.PROHIBITED if _ich_like(reg) else LS.PHYSICIAN_DISCRETION_GRAY,
            pathway=AP.NONE if _ich_like(reg) else AP.MEDICAL_TOURISM_CASH,
            authority=auth,
            legal_basis="Inferred: ozone therapy is generally not an approved medical therapy in strict regulators; gray abroad.",
            details="US FDA has warned against ozone therapy for disease treatment.",
            summary="Inferred unlawful or non-recognized as medical therapy in strict markets.",
            eligibility="None in strict markets.",
            provider="No lawful medical therapy pathway inferred in ICH-class systems.",
            oversight=OQ.HIGH if _ich_like(reg) else OQ.MINIMAL,
            confidence=CF.MODERATE if _ich_like(reg) else CF.LOW,
        )

    # ── General medical fallback ──────────────────────────────────────────
    return _cell(
        proc_id, jur_id,
        legal_status=LS.PHYSICIAN_DISCRETION_GRAY, pathway=AP.OFF_LABEL_PRESCRIPTION,
        authority=auth,
        legal_basis="Inferred general medical-practice fallback — no therapy-class-specific rule matched strongly.",
        details="Treat as requiring local medical board and medicines-law confirmation.",
        summary="Inferred gray/general practice posture — low confidence; research required.",
        eligibility="Clinician judgment.",
        provider="Licensed clinician; confirm product legality.",
        oversight=OQ.VARIABLE, confidence=CF.LOW,
    )


def build_inferred_access_records(
    existing_pairs: set,
    *,
    procedures: list,
    jurisdictions: list,
) -> list:
    """
    procedures: iterable of objects/dicts with id, name, modality/regulatory_modality,
                default_global_posture, controlled_substance_class
    jurisdictions: iterable with id, parent_id, regulation_json (str or dict or None)
    """
    out = []
    pairs = set(existing_pairs)

    def proc_get(p, key, default=None):
        if isinstance(p, dict):
            return p.get(key, default)
        return getattr(p, key, default)

    def jur_get(j, key, default=None):
        if isinstance(j, dict):
            return j.get(key, default)
        return getattr(j, key, default)

    for p in procedures:
        pid = proc_get(p, "id")
        if not pid:
            continue
        modality = proc_get(p, "regulatory_modality") or proc_get(p, "modality") or ""
        if hasattr(modality, "value"):
            modality = modality.value
        posture = proc_get(p, "default_global_posture") or ""
        if hasattr(posture, "value"):
            posture = posture.value
        pname = proc_get(p, "name") or pid

        for j in jurisdictions:
            jid = jur_get(j, "id")
            if not jid:
                continue
            key = (pid, jid)
            if key in pairs:
                continue
            parent_id = jur_get(j, "parent_id")
            reg_raw = jur_get(j, "regulation_json")
            reg_json = None
            if isinstance(reg_raw, dict):
                reg_json = reg_raw
            elif isinstance(reg_raw, str) and reg_raw.strip():
                try:
                    reg_json = json.loads(reg_raw)
                except Exception:
                    reg_json = None

            rec = infer_for_pair(
                pid, jid,
                modality=str(modality or ""),
                posture=str(posture or ""),
                parent_id=parent_id,
                jur_reg_json=reg_json,
                proc_name=pname,
            )
            if not rec:
                continue
            pairs.add(key)
            out.append(rec)
    return out
