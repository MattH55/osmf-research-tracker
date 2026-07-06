"""Compact remission statistics strip for disease page hero banners."""
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


HERO_REMISSION_CSS = """
    .hero-remission-strip{display:flex;flex-wrap:wrap;justify-content:center;align-items:stretch;gap:.75rem;max-width:1040px;margin:1.5rem auto 0;padding-top:1.25rem;border-top:1px solid rgba(42,48,80,.45)}
    .hero-rem-stat{background:rgba(20,24,40,.55);border:1px solid var(--border);border-radius:8px;padding:.7rem 1rem;text-align:left;min-width:160px;max-width:260px;flex:1 1 160px}
    .hero-rem-primary{border-color:rgba(74,158,255,.35);background:rgba(74,158,255,.06)}
    .hero-rem-label{display:block;font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem;font-weight:600}
    .hero-rem-value{display:block;font-size:.82rem;line-height:1.4;color:var(--text)}
    .hero-rem-link{align-self:center;font-size:.8rem;color:var(--accent)!important;white-space:nowrap;padding:.5rem .25rem;flex:0 0 auto}
    .hero-rem-link:hover{text-decoration:underline!important}
    @media(max-width:640px){.hero-remission-strip{flex-direction:column;align-items:stretch}.hero-rem-stat{max-width:none}.hero-rem-link{text-align:center;padding-top:.25rem}}
"""