"""Compact hero banner strips — remission and disease burden."""
from __future__ import annotations

import html
import re


def _esc(text: str | None) -> str:
    return html.escape(str(text or ""))


def _truncate(text: str, max_len: int = 120) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0]
    return (cut or text[: max_len - 1]).rstrip(" ,;") + "…"


def hero_remission_html(
    rem: dict | None,
    *,
    detail_anchor: str = "#remission",
    max_len: int = 120,
) -> str:
    """Render a compact remission stats row for the page-hero banner."""
    if not rem:
        return ""

    spont = rem.get("spontaneous_remission_rate")
    best = rem.get("best_intervention_remission_rate")
    gap = rem.get("gap_size")
    barrier = rem.get("barrier_type") or rem.get("primary_barrier")

    if not any([spont, best, gap, barrier]):
        return ""

    def stat(label: str, value: str | None, *, primary: bool = False) -> str:
        if not value:
            return ""
        cls = "hero-rem-stat hero-rem-primary" if primary else "hero-rem-stat"
        return (
            f'<div class="{cls}">'
            f'<span class="hero-rem-label">{_esc(label)}</span>'
            f'<span class="hero-rem-value">{_esc(_truncate(str(value), max_len))}</span>'
            f"</div>"
        )

    cells = "".join([
        stat("Spontaneous remission", spont, primary=True),
        stat("Best-intervention remission", best, primary=True),
        stat("Gap size", gap),
        stat("Primary barrier", barrier),
    ])
    if not cells:
        return ""

    link = ""
    if detail_anchor:
        link = (
            f'<a href="{_esc(detail_anchor)}" class="hero-rem-link">'
            f"Full remission profile →</a>"
        )

    return f'<div class="hero-remission-strip">{cells}{link}</div>'


def _fmt_num(n: float | int | None) -> str | None:
    if n is None:
        return None
    try:
        v = float(n)
    except (TypeError, ValueError):
        return None
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if v >= 10_000:
        return f"{v / 1_000:.1f}K"
    if v >= 100:
        return f"{v:,.0f}"
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}"


def _fmt_dollars_m(millions: float | int | None) -> str | None:
    if millions is None or str(millions) in ("-", "+"):
        return None
    try:
        m = float(millions)
    except (TypeError, ValueError):
        return None
    if m >= 1000:
        return f"${m / 1000:.2f}B"
    return f"${m:.0f}M"


def _funding_level_label(level: str | None) -> str | None:
    if not level or level == "unknown":
        return None
    return level.replace("_", " ").title()


def _burden_year(burden: dict) -> int:
    return int(burden.get("ghe_year") or burden.get("gbd_year") or 2021)


def _burden_source(burden: dict) -> str:
    if burden.get("ghe_cause") or burden.get("source") == "WHO GHE":
        return "WHO GHE"
    if burden.get("gbd_cause_id") or burden.get("source") == "IHME GBD":
        return "IHME GBD"
    return str(burden.get("source") or "WHO GHE")


def hero_burden_html(burden: dict | None) -> str:
    """Render US/global DALYs, mortality, NIH funding, and funding level in the hero."""
    if not burden:
        return ""

    cells: list[str] = []
    year = _burden_year(burden)
    source = _burden_source(burden)

    us_dalys = burden.get("us_dalys")
    if us_dalys:
        cells.append(
            f'<div class="hero-burden-stat hero-burden-primary">'
            f'<span class="hero-burden-label">US DALYs</span>'
            f'<span class="hero-burden-value">{_esc(_fmt_num(us_dalys))}</span>'
            f'<span class="hero-burden-sub">{source} {year} · all ages</span>'
            f"</div>"
        )

    global_dalys = burden.get("global_dalys")
    if global_dalys:
        cells.append(
            f'<div class="hero-burden-stat hero-burden-primary">'
            f'<span class="hero-burden-label">Global DALYs</span>'
            f'<span class="hero-burden-value">{_esc(_fmt_num(global_dalys))}</span>'
            f'<span class="hero-burden-sub">{source} {year} · worldwide</span>'
            f"</div>"
        )

    us_deaths = burden.get("us_deaths")
    if us_deaths and float(us_deaths) >= 1:
        cells.append(
            f'<div class="hero-burden-stat">'
            f'<span class="hero-burden-label">US mortality</span>'
            f'<span class="hero-burden-value">{_esc(_fmt_num(us_deaths))} deaths/yr</span>'
            f'<span class="hero-burden-sub">{source} {year}</span>'
            f"</div>"
        )

    global_deaths = burden.get("global_deaths")
    if global_deaths and float(global_deaths) >= 1:
        cells.append(
            f'<div class="hero-burden-stat">'
            f'<span class="hero-burden-label">Global mortality</span>'
            f'<span class="hero-burden-value">{_esc(_fmt_num(global_deaths))} deaths/yr</span>'
            f'<span class="hero-burden-sub">{source} {year} · worldwide</span>'
            f"</div>"
        )

    funding = _fmt_dollars_m(burden.get("nih_funding_millions_usd"))
    if funding:
        fy = burden.get("nih_fiscal_year", 2025)
        cells.append(
            f'<div class="hero-burden-stat hero-burden-primary">'
            f'<span class="hero-burden-label">NIH funding</span>'
            f'<span class="hero-burden-value">{_esc(funding)}</span>'
            f'<span class="hero-burden-sub">FY{fy} · RCDC estimate</span>'
            f"</div>"
        )

    level = _funding_level_label(burden.get("funding_level"))
    if level:
        cls = "hero-burden-stat"
        if "underfund" in (burden.get("funding_level") or ""):
            cls += " hero-burden-alert"
        cells.append(
            f'<div class="{cls}">'
            f'<span class="hero-burden-label">Funding level</span>'
            f'<span class="hero-burden-value">{_esc(level)}</span>'
            f"</div>"
        )

    if not cells:
        return ""

    return f'<div class="hero-burden-strip">{"".join(cells)}</div>'


HERO_REMISSION_CSS = """
    .hero-remission-strip{display:flex;flex-wrap:wrap;justify-content:center;align-items:stretch;gap:.75rem;max-width:1040px;margin:1.5rem auto 0;padding-top:1.25rem;border-top:1px solid rgba(42,48,80,.45)}
    .hero-rem-stat{background:rgba(20,24,40,.55);border:1px solid var(--border);border-radius:8px;padding:.7rem 1rem;text-align:left;min-width:160px;max-width:260px;flex:1 1 160px}
    .hero-rem-primary{border-color:rgba(74,158,255,.35);background:rgba(74,158,255,.06)}
    .hero-rem-label{display:block;font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem;font-weight:600}
    .hero-rem-value{display:block;font-size:.82rem;line-height:1.4;color:var(--text)}
    .hero-rem-link{align-self:center;font-size:.8rem;color:var(--accent)!important;white-space:nowrap;padding:.5rem .25rem;flex:0 0 auto}
    .hero-rem-link:hover{text-decoration:underline!important}
    @media(max-width:640px){.hero-remission-strip{flex-direction:column;align-items:stretch}.hero-rem-stat{max-width:none}.hero-rem-link{text-align:center;padding-top:.25rem}}
    .hero-burden-strip{display:flex;flex-wrap:wrap;justify-content:center;align-items:stretch;gap:.75rem;max-width:1040px;margin:1rem auto 0;padding-top:1rem;border-top:1px solid rgba(42,48,80,.35)}
    .hero-burden-stat{background:rgba(20,24,40,.45);border:1px solid var(--border);border-radius:8px;padding:.65rem 1rem;text-align:center;min-width:130px;max-width:200px;flex:1 1 130px}
    .hero-burden-primary{border-color:rgba(124,106,247,.35);background:rgba(124,106,247,.08)}
    .hero-burden-alert{border-color:rgba(245,158,11,.4);background:rgba(245,158,11,.08)}
    .hero-burden-label{display:block;font-size:.66rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.25rem;font-weight:600}
    .hero-burden-value{display:block;font-size:.95rem;font-weight:700;line-height:1.3;color:var(--text)}
    .hero-burden-sub{display:block;font-size:.68rem;color:var(--muted);margin-top:.2rem}
    @media(max-width:640px){.hero-burden-strip{flex-direction:column;align-items:stretch}.hero-burden-stat{max-width:none}}
"""