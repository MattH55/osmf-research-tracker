#!/usr/bin/env python3
"""
Ticket 2 — Thin-content gate as a reusable script.

Provides a `gate()` function that checks a page against all 3 rules from
strategy doc §4, and a `--report` CLI mode for auditing a corpus of pages.

Rules:
  1. Word count of unique prose >= min_words
  2. 5-gram shingle overlap vs every other already-built page's prose <= 70%
  3. At least one citation with a resolvable PMID or DOI

Usage as library:
  from scripts.lib.thin_content_gate import gate, ThinContentResult
  result = gate(page_text, min_words=250, corpus_dir="disease-intelligence/")
  if not result.indexable:
      # write <meta name="robots" content="noindex,follow">

Usage as CLI reporter:
  python scripts/lib/thin_content_gate.py --report --min-words 250 disease-intelligence/
"""

import os, re, sys, json, argparse
from pathlib import Path
from typing import List, Set, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class ThinContentResult:
    indexable: bool
    reasons: List[str] = field(default_factory=list)
    meta_robots: str = "index,follow"       # default; set to noindex,follow on failure
    word_count: int = 0
    max_overlap_pct: float = 0.0
    overlapping_file: Optional[str] = None
    has_citation: bool = False


# ---------------------------------------------------------------------------
# Helper: extract prose text from an HTML page
# ---------------------------------------------------------------------------

SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "template"}

def extract_prose(html_path: Path) -> str:
    """Read an HTML file and return the concatenated visible text, excluding
    nav/footer/script/style boilerplate."""
    import html as _html
    from html.parser import HTMLParser

    class ProseExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text_parts: List[str] = []
            self.skip_depth = 0

        def handle_starttag(self, tag, attrs):
            if tag.lower() in SKIP_TAGS:
                self.skip_depth += 1

        def handle_endtag(self, tag):
            if tag.lower() in SKIP_TAGS and self.skip_depth > 0:
                self.skip_depth -= 1

        def handle_data(self, data):
            if self.skip_depth == 0:
                t = data.strip()
                if t:
                    self.text_parts.append(t)

    raw = html_path.read_text(encoding="utf-8", errors="replace")
    extractor = ProseExtractor()
    extractor.feed(raw)
    return " ".join(extractor.text_parts)


def extract_prose_from_string(html_string: str) -> str:
    """Same as extract_prose but takes a string instead of a file path."""
    import tempfile
    import atexit
    fd, path = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    try:
        Path(path).write_text(html_string, encoding="utf-8")
        return extract_prose(Path(path))
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Rule 1: word count
# ---------------------------------------------------------------------------

def _word_count(prose: str) -> int:
    return len(re.findall(r"\b\w+\b", prose))


# ---------------------------------------------------------------------------
# Rule 2: 5-gram shingle overlap
# ---------------------------------------------------------------------------

def _ngrams(words: List[str], n: int = 5) -> Set[str]:
    return {" ".join(words[i:i+n]) for i in range(len(words) - n + 1)}


def _jaccard_overlap(grams_a: Set[str], grams_b: Set[str]) -> float:
    if not grams_a and not grams_b:
        return 0.0
    intersection = grams_a & grams_b
    union = grams_a | grams_b
    if not union:
        return 0.0
    return len(intersection) / len(union)


def _check_overlap(
    prose: str,
    corpus_dir: str,
) -> Tuple[float, Optional[str]]:
    """Return (max_overlap_pct, overlapping_file) against all other pages in corpus_dir."""
    words_a = re.findall(r"\b\w+\b", prose.lower())
    grams_a = _ngrams(words_a, 5)
    if not grams_a:
        return 0.0, None

    max_pct = 0.0
    max_file = None
    corpus = Path(corpus_dir).glob("*.html")
    for fp in corpus:
        other_prose = extract_prose(fp)
        words_b = re.findall(r"\b\w+\b", other_prose.lower())
        grams_b = _ngrams(words_b, 5)
        if not grams_b:
            continue
        pct = _jaccard_overlap(grams_a, grams_b) * 100.0
        if pct > max_pct:
            max_pct = pct
            max_file = str(fp)

    return max_pct, max_file


# ---------------------------------------------------------------------------
# Rule 3: citation check (PMID or DOI)
# ---------------------------------------------------------------------------

PMID_RE = re.compile(r"\bPMID\s*[:=]?\s*(\d{7,8})\b", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,}/[^\s\"\'<>]+", re.IGNORECASE)
CITATION_HREF_RE = re.compile(
    r"""href\s*=\s*["'][^"']*(?:doi\.org/10\.\d{4,}|ncbi\.nlm\.nih\.gov/pubmed/\d+|pubmed\.ncbi\.nlm\.nih\.gov/\d+)[^"']*["']""",
    re.IGNORECASE,
)

def _has_citation(prose: str, raw_html: Optional[str] = None) -> bool:
    if PMID_RE.search(prose) or DOI_RE.search(prose):
        return True
    # Citations are frequently rendered as visible links whose anchor text is a
    # generic label ("Citation", "View study") with the PMID/DOI only in the
    # href attribute — visible-text extraction misses those, so also check the
    # raw markup for a citation-shaped href.
    if raw_html and CITATION_HREF_RE.search(raw_html):
        return True
    return False


# ---------------------------------------------------------------------------
# Main gate function
# ---------------------------------------------------------------------------

def gate(
    page_text: str,
    min_words: int = 250,
    corpus_dir: Optional[str] = None,
) -> ThinContentResult:
    """Run all 3 gating rules against a page's HTML text.

    Args:
        page_text: Full HTML string of the page to check.
        min_words: Minimum unique prose word count required (250 for A, 200 for B/C, 150 for D).
        corpus_dir: Directory of already-built HTML pages to check against for overlap.
                    If None, overlap check is skipped.

    Returns ThinContentResult with indexable=True only if all checks pass.
    """
    prose = extract_prose_from_string(page_text)
    result = ThinContentResult(indexable=True)

    # Rule 1: word count
    wc = _word_count(prose)
    result.word_count = wc
    if wc < min_words:
        result.reasons.append(
            f"Word count {wc} below minimum {min_words}"
        )
        result.indexable = False

    # Rule 2: 5-gram overlap
    if corpus_dir and os.path.isdir(corpus_dir):
        max_overlap, overlap_file = _check_overlap(prose, corpus_dir)
        result.max_overlap_pct = round(max_overlap, 1)
        result.overlapping_file = overlap_file
        if max_overlap > 70.0:
            result.reasons.append(
                f"Max 5-gram overlap {max_overlap:.1f}% with {overlap_file} exceeds 70%"
            )
            result.indexable = False

    # Rule 3: citation
    has_cit = _has_citation(prose, raw_html=page_text)
    result.has_citation = has_cit
    if not has_cit:
        result.reasons.append("No resolvable PMID or DOI citation found")
        result.indexable = False

    # Set meta robots
    result.meta_robots = "index,follow" if result.indexable else "noindex,follow"

    return result


# ---------------------------------------------------------------------------
# CLI --report mode
# ---------------------------------------------------------------------------

def report(corpus_dir: str, min_words: int = 250):
    """Print a table of (page, word_count, overlap_pct, has_citation, indexable)."""
    header = f"{'Page':<60} {'Words':>6} {'Overlap%':>8} {'Citation':>8} {'Indexable':>10}"
    print(header)
    print("-" * len(header))

    corpus = sorted(Path(corpus_dir).glob("*.html"))
    # Build prose cache to avoid re-reading every file per-page for overlap
    prose_cache: dict[str, str] = {}
    for fp in corpus:
        prose_cache[str(fp)] = extract_prose(fp)

    for fp in corpus:
        page_text = fp.read_text(encoding="utf-8", errors="replace")
        result = gate(page_text, min_words=min_words, corpus_dir=corpus_dir)
        idx = "YES" if result.indexable else "NO"
        print(
            f"{fp.name:<60} {result.word_count:>6} "
            f"{result.max_overlap_pct:>7.1f}% "
            f"{'Yes' if result.has_citation else 'No':>8} "
            f"{idx:>10}"
        )
        if not result.indexable:
            for reason in result.reasons:
                print(f"  -> {reason}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thin-content gate checker")
    parser.add_argument("--report", action="store_true", help="Produce a corpus audit table")
    parser.add_argument("--min-words", type=int, default=250, help="Minimum prose word count")
    parser.add_argument("corpus_dir", nargs="?", default=None, help="Directory of HTML files")
    args = parser.parse_args()

    if args.report:
        if not args.corpus_dir:
            print("ERROR: --report requires a corpus_dir", file=sys.stderr)
            sys.exit(1)
        report(args.corpus_dir, args.min_words)
    else:
        # Single-file gate mode
        import fileinput
        text = "".join(fileinput.input(files=sys.argv[1:] if len(sys.argv) > 1 else None))
        result = gate(text, min_words=args.min_words, corpus_dir=args.corpus_dir)
        print(json.dumps({
            "indexable": result.indexable,
            "meta_robots": result.meta_robots,
            "word_count": result.word_count,
            "max_overlap_pct": result.max_overlap_pct,
            "overlapping_file": result.overlapping_file,
            "has_citation": result.has_citation,
            "reasons": result.reasons,
        }, indent=2))
        sys.exit(0 if result.indexable else 1)