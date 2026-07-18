"""Watchlist digest: build change reports and optionally send email.

Supports:
  - RESEND_API_KEY + RESEND_FROM (preferred on free hosting)
  - SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / SMTP_FROM
  - Fallback: log-only (returns digest text; no send)

DIGEST_SECRET protects bulk send endpoint when set.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import smtplib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from .access_flags import compute_access_flags
from .models import AccessRecord, Jurisdiction, Procedure, WatchSubscription


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email.strip()) and len(email) < 320)


def new_unsub_token() -> str:
    return secrets.token_urlsafe(24)


def _verdict_label(ar: AccessRecord) -> str:
    flags = compute_access_flags(ar.legal_status, ar.access_pathway, ar.volatility)
    if flags.get("prohibited"):
        return "Blocked"
    if flags.get("allowed") and flags.get("offered") and not flags.get("trial_only"):
        if flags.get("pending_legislation") or flags.get("active_flux"):
            return "Open — policy risk"
        return "Open to license"
    if flags.get("trial_only"):
        return "Trial-site only"
    if flags.get("allowed"):
        return "Lawful, no pathway"
    if flags.get("offered"):
        return "Gray / cash path"
    return "Unclear"


def _cell_key(proc_id: str, jur_id: str) -> str:
    return f"{proc_id}::{jur_id}"


def resolve_watch_items(db, items: list[dict]) -> list[dict]:
    """Enrich watch items with live verdict, confidence, last_verified."""
    out = []
    for it in items or []:
        pid = it.get("procedure_id") or it.get("therapyId")
        jid = it.get("jurisdiction_id") or it.get("jurId")
        if not pid or not jid:
            continue
        ar = (
            db.query(AccessRecord)
            .filter(AccessRecord.procedure_id == pid, AccessRecord.jurisdiction_id == jid)
            .first()
        )
        proc = db.query(Procedure).filter(Procedure.id == pid).first()
        jur = db.query(Jurisdiction).filter(Jurisdiction.id == jid).first()
        row = {
            "procedure_id": pid,
            "jurisdiction_id": jid,
            "procedure_name": (proc.name if proc else None) or it.get("procedure_name") or it.get("therapyName") or pid,
            "jurisdiction_name": (jur.name if jur else None) or it.get("jurisdiction_name") or it.get("jurName") or jid,
            "found": bool(ar),
            "verdict": None,
            "legal_status": None,
            "confidence": None,
            "last_verified": None,
            "verified_by": None,
            "volatility": None,
            "setup_difficulty": None,
        }
        if ar:
            row["verdict"] = _verdict_label(ar)
            row["legal_status"] = ar.legal_status.value if hasattr(ar.legal_status, "value") else ar.legal_status
            row["confidence"] = ar.confidence.value if hasattr(ar.confidence, "value") else ar.confidence
            row["last_verified"] = ar.last_verified.isoformat() if ar.last_verified else None
            row["verified_by"] = ar.verified_by
            row["volatility"] = ar.volatility.value if hasattr(ar.volatility, "value") else ar.volatility
            try:
                setup = json.loads(ar.setup_requirements) if ar.setup_requirements else {}
                row["setup_difficulty"] = setup.get("difficulty")
            except Exception:
                pass
        prev = it.get("last_verdict") or it.get("lastVerdict")
        row["previous_verdict"] = prev
        row["changed"] = bool(prev and row["verdict"] and prev != row["verdict"])
        out.append(row)
    return out


def build_digest_text(email: str, resolved: list[dict], *, base_url: str = "", unsub_token: str = "") -> str:
    changed = [r for r in resolved if r.get("changed")]
    lines = [
        "MedFreedom Provider Map — Watchlist digest",
        f"To: {email}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]
    if changed:
        lines.append(f"CHANGES ({len(changed)}):")
        for r in changed:
            lines.append(
                f"  • {r['procedure_name']} · {r['jurisdiction_name']}: "
                f"{r.get('previous_verdict')} → {r.get('verdict')}"
            )
        lines.append("")
    else:
        lines.append("No operability status changes since your last snapshot.")
        lines.append("")

    lines.append(f"WATCHED MARKETS ({len(resolved)}):")
    for r in resolved:
        conf = r.get("confidence") or "—"
        verified = r.get("last_verified") or "not dated"
        flag = " [CHANGED]" if r.get("changed") else ""
        missing = " [cell not found]" if not r.get("found") else ""
        lines.append(
            f"  • {r['procedure_name']} · {r['jurisdiction_name']}: "
            f"{r.get('verdict') or '—'}{flag}{missing}"
        )
        lines.append(
            f"      confidence={conf} · last_verified={verified}"
            f"{(' · setup=' + r['setup_difficulty']) if r.get('setup_difficulty') else ''}"
        )
        if base_url and r.get("procedure_id") and r.get("jurisdiction_id"):
            lines.append(
                f"      {base_url.rstrip('/')}/?therapy={r['procedure_id']}&jur={r['jurisdiction_id']}"
            )
    lines.append("")
    lines.append("Not legal advice. Confirm with counsel and the competent authority.")
    if base_url and unsub_token:
        lines.append(f"Unsubscribe: {base_url.rstrip('/')}/api/watch/unsubscribe?token={unsub_token}")
    lines.append("— MedFreedom · Open Source Medicine Foundation")
    return "\n".join(lines)


def build_digest_html(email: str, resolved: list[dict], *, base_url: str = "", unsub_token: str = "") -> str:
    changed = [r for r in resolved if r.get("changed")]
    parts = [
        "<h2>MedFreedom watchlist digest</h2>",
        f"<p>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>",
    ]
    if changed:
        parts.append(f"<h3>Changes ({len(changed)})</h3><ul>")
        for r in changed:
            parts.append(
                f"<li><strong>{_esc(r['procedure_name'])}</strong> · {_esc(r['jurisdiction_name'])}: "
                f"{_esc(r.get('previous_verdict'))} → <strong>{_esc(r.get('verdict'))}</strong></li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>No operability status changes since your last snapshot.</p>")

    parts.append(f"<h3>All watched markets ({len(resolved)})</h3><ul>")
    for r in resolved:
        link = ""
        if base_url and r.get("procedure_id") and r.get("jurisdiction_id"):
            href = f"{base_url.rstrip('/')}/?therapy={r['procedure_id']}&jur={r['jurisdiction_id']}"
            link = f' — <a href="{_esc(href)}">Open</a>'
        ch = " <em>(changed)</em>" if r.get("changed") else ""
        parts.append(
            f"<li><strong>{_esc(r['procedure_name'])}</strong> · {_esc(r['jurisdiction_name'])}: "
            f"{_esc(r.get('verdict') or '—')}{ch}"
            f"<br/><small>confidence={_esc(r.get('confidence') or '—')} · "
            f"verified={_esc(r.get('last_verified') or 'not dated')}</small>{link}</li>"
        )
    parts.append("</ul>")
    parts.append("<p><small>Not legal advice. MedFreedom · Open Source Medicine Foundation</small></p>")
    if base_url and unsub_token:
        u = f"{base_url.rstrip('/')}/api/watch/unsubscribe?token={unsub_token}"
        parts.append(f'<p><small><a href="{_esc(u)}">Unsubscribe</a></small></p>')
    return "\n".join(parts)


def _esc(s: Any) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def email_configured() -> dict:
    resend = bool(os.getenv("RESEND_API_KEY"))
    smtp = bool(os.getenv("SMTP_HOST"))
    return {
        "configured": resend or smtp,
        "provider": "resend" if resend else ("smtp" if smtp else "none"),
        "from": os.getenv("RESEND_FROM") or os.getenv("SMTP_FROM") or None,
    }


def send_email(to: str, subject: str, text_body: str, html_body: Optional[str] = None) -> dict:
    """Send email via Resend or SMTP. Returns {ok, method, detail}."""
    cfg = email_configured()
    if not cfg["configured"]:
        return {"ok": False, "method": "none", "detail": "No RESEND_API_KEY or SMTP_HOST configured"}

    if os.getenv("RESEND_API_KEY"):
        return _send_resend(to, subject, text_body, html_body)
    return _send_smtp(to, subject, text_body, html_body)


def _send_resend(to: str, subject: str, text_body: str, html_body: Optional[str]) -> dict:
    api_key = os.getenv("RESEND_API_KEY")
    from_addr = os.getenv("RESEND_FROM", "MedFreedom <onboarding@resend.dev>")
    payload = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "method": "resend", "detail": body[:500]}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "method": "resend", "detail": f"HTTP {e.code}: {err[:500]}"}
    except Exception as e:
        return {"ok": False, "method": "resend", "detail": str(e)}


def _send_smtp(to: str, subject: str, text_body: str, html_body: Optional[str]) -> dict:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT") or "587")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM") or user or "noreply@medfreedom.local"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            if os.getenv("SMTP_TLS", "1") not in ("0", "false", "False"):
                server.starttls()
                server.ehlo()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        return {"ok": True, "method": "smtp", "detail": f"sent via {host}:{port}"}
    except Exception as e:
        return {"ok": False, "method": "smtp", "detail": str(e)}


def snapshot_from_resolved(resolved: list[dict]) -> dict:
    return {
        _cell_key(r["procedure_id"], r["jurisdiction_id"]): r.get("verdict")
        for r in resolved
        if r.get("procedure_id") and r.get("jurisdiction_id")
    }


def apply_snapshot_to_items(items: list[dict], snapshot: dict) -> list[dict]:
    """Attach last_verdict from snapshot for change detection."""
    out = []
    for it in items or []:
        d = dict(it)
        pid = d.get("procedure_id") or d.get("therapyId")
        jid = d.get("jurisdiction_id") or d.get("jurId")
        if pid and jid and snapshot:
            prev = snapshot.get(_cell_key(pid, jid))
            if prev:
                d["last_verdict"] = prev
        out.append(d)
    return out


def upsert_subscription(db, email: str, items: list[dict], frequency: str = "weekly") -> WatchSubscription:
    email = email.strip().lower()
    freq = frequency if frequency in ("weekly", "daily") else "weekly"
    # Normalize items
    norm = []
    for it in items or []:
        pid = it.get("procedure_id") or it.get("therapyId")
        jid = it.get("jurisdiction_id") or it.get("jurId")
        if not pid or not jid:
            continue
        norm.append({
            "procedure_id": pid,
            "jurisdiction_id": jid,
            "procedure_name": it.get("procedure_name") or it.get("therapyName"),
            "jurisdiction_name": it.get("jurisdiction_name") or it.get("jurName"),
            "last_verdict": it.get("last_verdict") or it.get("lastVerdict"),
        })
    sub = (
        db.query(WatchSubscription)
        .filter(WatchSubscription.email == email, WatchSubscription.active.is_(True))
        .first()
    )
    now = datetime.now(timezone.utc)
    if sub:
        # Merge items by key
        existing = json.loads(sub.items_json) if sub.items_json else []
        by_key = {_cell_key(i["procedure_id"], i["jurisdiction_id"]): i for i in existing if i.get("procedure_id")}
        for n in norm:
            by_key[_cell_key(n["procedure_id"], n["jurisdiction_id"])] = n
        sub.items_json = json.dumps(list(by_key.values()))
        sub.frequency = freq
    else:
        sub = WatchSubscription(
            email=email,
            items_json=json.dumps(norm),
            frequency=freq,
            active=True,
            created_at=now,
            unsubscribe_token=new_unsub_token(),
        )
        db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub
