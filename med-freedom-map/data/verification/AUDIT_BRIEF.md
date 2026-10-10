# Quote audit brief

An automated checker could not find these evidence quotes on their cited pages, usually because the page is a PDF, a JavaScript app, a bot-blocked site, or an API/JSON response. Your job is to decide, by reading each page yourself, whether each quote is genuinely on it.

Input: `batches\audit-N.jsonl`, one line per quote: `{batch, key, url, quote}`. Lines are grouped by URL; fetch each URL once (WebFetch; for timeouts or blocks try `https://web.archive.org/web/2026/<url>`; for PDFs read the text WebFetch returns or extract it from the downloaded file).

Output: `results\audit-N.jsonl`, one line per input line, appended 10–20 at a time:
```json
{"key":"<same>","url":"<same>","quote":"<same, unchanged>","verdict":"present|paraphrase|absent|unreadable",
 "verbatim":"if paraphrase: the exact sentence(s) from the page (≤40 words) that state the same fact; else omit",
 "note":"short"}
```
- `present`: the quote's words appear on the page (ignore whitespace, punctuation, case, and "..." joins between real fragments).
- `paraphrase`: the page states the same fact but the quote's wording is not on the page. Give the real wording in `verbatim`.
- `absent`: the page does not state that fact (or states something different).
- `unreadable`: you could not read the page by any route. Do not guess.

Be strict and literal. Never edit any other file. Use at most ~30 WebSearch calls (you mostly need WebFetch). When done, confirm one output line per input line and report counts per verdict (max 120 words).
