from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
urls = ["https://research.opensourcemed.info/ntd/index.html"]
for p in sorted((ROOT / "ntd").glob("*.html")):
    if p.name != "index.html":
        urls.append(f"https://research.opensourcemed.info/ntd/{p.name}")

lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
]
for u in urls:
    lines.extend([
        "  <url>",
        f"    <loc>{u}</loc>",
        "    <lastmod>2026-07-09</lastmod>",
        "    <changefreq>monthly</changefreq>",
        "    <priority>0.85</priority>",
        "  </url>",
    ])
lines.append("</urlset>")
(ROOT / "ntd.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {len(urls)} URLs to ntd.xml")