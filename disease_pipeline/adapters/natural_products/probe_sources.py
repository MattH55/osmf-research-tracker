#!/usr/bin/env python3
"""Probe Examine.com and GreenMedInfo page structure."""
from __future__ import annotations

import re
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def probe_gmi(slug: str = "type-2-diabetes") -> None:
    url = f"https://www.greenmedinfo.com/disease/{slug}"
    html = fetch(url)
    print("GMI", url, "bytes", len(html))
    substances = sorted(set(re.findall(r'href="(/substance/[^"]+)"', html)))
    print("substance links", len(substances))
    for s in substances[:25]:
        print(" ", s)
    remedies = re.findall(r'class="remedy[^"]*"[^>]*>([^<]+)<', html)
    print("remedy class hits", len(remedies), remedies[:10])


def probe_examine(slug: str = "type-2-diabetes") -> None:
    for path in (f"conditions/{slug}/", f"topics/{slug}/", f"search/?q={slug}"):
        url = f"https://examine.com/{path}"
        try:
            html = fetch(url)
            print("Examine OK", url, len(html), html[:200].replace("\n", " "))
        except Exception as e:
            print("Examine FAIL", url, e)


if __name__ == "__main__":
    probe_gmi()
    probe_examine()