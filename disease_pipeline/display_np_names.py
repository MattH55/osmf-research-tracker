"""Professional display capitalization for natural product names."""
from __future__ import annotations

import re

from .adapters.natural_products.normalize_np import load_np_synonyms, load_np_synonyms_data

_SMALL_WORDS = frozenset({
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with", "vs", "vs.",
})
_ACRONYMS = frozenset({
    "EGCG", "NAC", "CLA", "DHA", "EPA", "HMB", "CBD", "THC", "GABA", "ATP", "BPA", "PCOS", "HIV", "RNA", "DNA",
    "CoQ10", "SAMe", "5-HTP", "GLA", "ALA", "PUFA", "MUFA", "ONOG",
})
_IUPAC_RE = re.compile(
    r"(\[\d|^\(|\btetracyclo\b|\bquinazolin|\bbenzo[d]?|\bpiperazino|\bimidazolin|\bchromen|\bcarboxamide\b|"
    r"\bmethanone\b|\bsulfonamide\b|\bphosphono\b|\btrimethyl\b|\bammonium\b|\bchloride\b|\bhydrate\b|"
    r"\d+,\d+-\d+|\[\d+\.\d+\])",
    re.I,
)


def is_systematic_chemistry_name(name: str) -> bool:
    """Heuristic: PubChem IUPAC / ChEMBL systematic strings."""
    if not name or len(name) < 12:
        return False
    if _IUPAC_RE.search(name):
        return True
    if name.count("-") >= 4 and re.search(r"\d", name):
        return True
    if len(name) > 72:
        return True
    return False


def _title_token(token: str, *, first: bool) -> str:
    if not token:
        return token
    bare = token.strip("()[]")
    upper = bare.upper()
    if upper in _ACRONYMS:
        return token.replace(bare, upper)
    if bare.isupper() and len(bare) > 2 and bare.isalpha():
        cased = bare.capitalize()
        return token.replace(bare, cased)
    if re.match(r"^[A-Za-z]\d", bare) or re.match(r"^\d", bare):
        return token
    lower = bare.lower()
    if not first and lower in _SMALL_WORDS:
        return token.replace(bare, lower)
    if "-" in bare:
        parts = bare.split("-")
        cased = "-".join(
            _title_token(p, first=(first and i == 0)) if p else p
            for i, p in enumerate(parts)
        )
        return token.replace(bare, cased)
    if bare.islower() or bare.isupper():
        return token.replace(bare, bare.capitalize())
    if bare[0].islower():
        return token.replace(bare, bare[0].upper() + bare[1:])
    return token


def professional_np_title(name: str) -> str:
    """Title-case supplement, botanical, and common compound names."""
    text = re.sub(r"\s+", " ", (name or "").strip())
    if not text:
        return text
    if is_systematic_chemistry_name(text):
        return text
    if text.isupper() and " " not in text and len(text) > 2:
        return text.capitalize()

    out: list[str] = []
    for i, word in enumerate(text.split(" ")):
        out.append(_title_token(word, first=(i == 0)))
    return " ".join(out)


def _synonym_canonical(name: str, canonical_id: str | None) -> str | None:
    data = load_np_synonyms_data()
    index = load_np_synonyms()

    for key in filter(None, (canonical_id, name)):
        k = key.lower().strip()
        hit = index.get(k)
        if hit:
            meta = data.get(hit, {})
            cname = (meta.get("canonical_name") or "").strip()
            if cname:
                if is_systematic_chemistry_name(cname):
                    return cname
                return professional_np_title(cname)
    return None


def _best_common_name(common_names: list[str] | None) -> str | None:
    if not common_names:
        return None
    ranked: list[tuple[int, str]] = []
    for raw in common_names:
        c = (raw or "").strip()
        if not c or c.lower() == "placebo":
            continue
        score = 0
        if is_systematic_chemistry_name(c):
            score -= 100
        if c.isupper() and len(c) <= 32:
            score += 40
        if 3 <= len(c) <= 48:
            score += 20
        if " " in c:
            score += 5
        ranked.append((score, c))
    if not ranked:
        return None
    ranked.sort(key=lambda x: (-x[0], len(x[1])))
    return ranked[0][1]


def resolve_np_display_name(
    name: str,
    *,
    common_names: list[str] | None = None,
    canonical_id: str | None = None,
) -> str:
    """Pick the best professional display label for a natural product."""
    raw = (name or "").strip()
    if not raw:
        return raw

    canonical = _synonym_canonical(raw, canonical_id)
    if canonical:
        return canonical

    if is_systematic_chemistry_name(raw):
        alt = _best_common_name(common_names)
        if alt and not is_systematic_chemistry_name(alt):
            return professional_np_title(alt)

    return professional_np_title(raw)


def format_np_row(row: dict) -> dict:
    """Return a copy of an exported NP row with normalized display name."""
    out = dict(row)
    display = resolve_np_display_name(
        out.get("name", ""),
        common_names=out.get("common_names"),
        canonical_id=out.get("canonical_id"),
    )
    out["name"] = display
    commons = out.get("common_names") or []
    if commons:
        formatted = []
        seen: set[str] = set()
        for c in commons:
            fc = resolve_np_display_name(c, canonical_id=out.get("canonical_id"))
            key = fc.lower()
            if key not in seen:
                seen.add(key)
                formatted.append(fc)
        if display.lower() not in seen:
            formatted.insert(0, display)
        out["common_names"] = formatted[:6]
    else:
        out["common_names"] = [display]
    ev = out.get("clinical_evidence")
    if isinstance(ev, dict) and ev.get("drug_name"):
        ev = dict(ev)
        ev["drug_name"] = display
        out["clinical_evidence"] = ev
    return out


def apply_np_names_to_web_data(data: dict) -> dict:
    """Normalize all natural_products names in a disease intelligence JSON blob."""
    nps = data.get("natural_products")
    if not nps:
        return data
    data["natural_products"] = [format_np_row(np) for np in nps]
    return data