"""Derive offered / allowed / legislation-watch flags for an access cell.

Schema intent (medical-freedom-arbitrage-schema §4):
  legal_status  = whether the law permits the thing
  access_pathway = whether you can actually get it
  volatility    = whether rules are about to change
"""
from typing import Any, Optional


PROHIBITED = {"Prohibited"}
UNKNOWN = {"Unknown", None, ""}
# Law allows some form of access (including trials, gray, decrim).
ALLOWED_STATUSES = {
    "Fully_Approved",
    "Approved_On_Label",
    "Approved_Off_Label",
    "Off_Label",
    "Regulated_Therapy_Program",
    "Right_To_Try",
    "Permitted_RTT",
    "Permitted_Expanded_Access",
    "Clinical_Trial_Only",
    "Physician_Discretion_Gray",
    "Unregulated_Permitted",
    "Decriminalized_Possession",
    "Decriminalized_No_Supply",
}
# Pathway implies a practical way to obtain treatment (not merely decrim/no supply).
OFFERED_PATHWAYS = {
    "Standard_Prescription",
    "Off_Label_Prescription",
    "Compounding",
    "Expanded_Access",
    "Right_To_Try",
    "Clinical_Trial_Enrollment",
    "Personal_Import",
    "Licensed_Provider_Regime",
    "Medical_Tourism_Cash",
}
TRIAL_PATHWAYS = {"Clinical_Trial_Enrollment"}
TRIAL_STATUSES = {"Clinical_Trial_Only"}
PENDING_VOL = {"Pending_Legislation"}
FLUX_VOL = {"Active_Flux", "Pending_Legislation"}


def _val(x: Any) -> Optional[str]:
    if x is None:
        return None
    return x.value if hasattr(x, "value") else str(x)


def compute_access_flags(
    legal_status=None,
    access_pathway=None,
    volatility=None,
) -> dict:
    legal = _val(legal_status)
    pathway = _val(access_pathway)
    vol = _val(volatility)

    prohibited = legal in PROHIBITED
    unknown = legal in UNKNOWN
    allowed = (not prohibited) and (legal in ALLOWED_STATUSES)

    # Decrim without supply: allowed to possess/use privately, not commercially offered.
    decrim_no_supply = legal in {"Decriminalized_No_Supply", "Decriminalized_Possession"} and (
        pathway in {None, "None", ""} or pathway == "None"
    )

    trial_only = (legal in TRIAL_STATUSES) or (pathway in TRIAL_PATHWAYS)
    pathway_offered = pathway in OFFERED_PATHWAYS
    offered = pathway_offered and not prohibited

    pending_legislation = vol in PENDING_VOL
    active_flux = vol == "Active_Flux"
    legislation_watch = vol in FLUX_VOL  # pending OR active flux

    # Composite labels for UI
    if prohibited:
        availability = "Not_Allowed"
    elif offered and trial_only:
        availability = "Offered_Trial_Only"
    elif offered and allowed:
        availability = "Allowed_And_Offered"
    elif allowed and not offered:
        availability = "Allowed_Not_Offered"
    elif offered and not allowed:
        availability = "Offered_Gray"  # rare: gray practice without clear allow
    else:
        availability = "Unknown"

    return {
        "allowed": bool(allowed),
        "offered": bool(offered),
        "trial_only": bool(trial_only),
        "decrim_no_supply": bool(decrim_no_supply),
        "prohibited": bool(prohibited),
        "pending_legislation": bool(pending_legislation),
        "active_flux": bool(active_flux),
        "legislation_watch": bool(legislation_watch),
        "availability": availability,
        "allowed_label": (
            "Prohibited" if prohibited
            else "Unknown" if unknown
            else "Trial only" if trial_only and allowed
            else "Allowed (decrim, limited supply)" if decrim_no_supply
            else "Allowed" if allowed
            else "Not clearly allowed"
        ),
        "offered_label": (
            "Not offered" if not offered
            else "Offered via clinical trials only" if trial_only
            else "Offered (licensed / cash / prescription pathway)"
        ),
        "legislation_label": (
            "Pending legislation" if pending_legislation
            else "Active policy flux" if active_flux
            else "Stable rules"
        ),
    }


def enrich_access_dict(d: dict) -> dict:
    """Attach flags onto an AccessRecord.to_dict()-style dict."""
    flags = compute_access_flags(
        d.get("legal_status"),
        d.get("access_pathway"),
        d.get("volatility"),
    )
    d["access_flags"] = flags
    return d
