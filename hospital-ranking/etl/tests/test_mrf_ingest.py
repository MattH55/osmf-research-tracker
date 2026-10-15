"""Offline unit tests: cms-hpt.txt parser, streaming CSV/JSON MRF parsers, extract
assembly and the offline-rebuild determinism of etl/ingest_mrf_prices.py.

Run: npm run test:etl   (python -m unittest discover -s etl/tests -v)
"""

from __future__ import annotations

import gzip
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ETL = Path(__file__).resolve().parents[1]
ROOT = ETL.parent
FIX = ROOT / "tests" / "fixtures" / "mrf"
sys.path.insert(0, str(ETL))

import ingest_mrf_prices as ing  # noqa: E402
from mrf_parsers import UnsupportedFormat, iter_mrf, looks_like_cms_hpt, parse_cms_hpt  # noqa: E402
from price_contract import CodeIndex, contract_problems, dump_json  # noqa: E402

CODES = CodeIndex()
KEEP = ing.make_keep(CODES)
HOSPITAL = {
    "id": "hosp-cms-990001", "cmsProviderId": "990001", "name": "West Mercy Hospital",
    "city": "Fullerton", "state": "CA", "zip": "92832", "hospitalType": "Acute Care Hospitals",
    "latitude": 33.87, "longitude": -117.92,
}
OTHER = {**HOSPITAL, "id": "hosp-cms-990002", "cmsProviderId": "990002", "name": "West Mercy Surgical Center"}


def by_desc(lines):
    return {ln["description"]: ln for ln in lines}


class CmsHptTests(unittest.TestCase):
    def test_parse_entries(self):
        text = (FIX / "cms-hpt.txt").read_text(encoding="utf-8")
        self.assertTrue(looks_like_cms_hpt(text))
        entries = parse_cms_hpt(text)
        self.assertEqual([e["location_name"] for e in entries], [
            "West Mercy Hospital", "West Mercy Surgical Center",
            "West Mercy Imaging (no blank line before this entry)"])
        self.assertEqual(entries[0]["mrf_url"], "https://www.westmercy.example/mrf/west-mercy_standardcharges.csv")
        self.assertEqual(entries[0]["source_page_url"], "https://www.westmercy.example/price-transparency")
        self.assertEqual(entries[0]["contact_email"], "pricing@westmercy.example")
        self.assertEqual(entries[2]["mrf_url"], "http://www.westmercy.example/mrf/imaging.csv")

    def test_html_is_not_cms_hpt(self):
        self.assertFalse(looks_like_cms_hpt("<html><body>mrf-url: x</body></html>"))
        self.assertFalse(looks_like_cms_hpt("User-agent: *\nDisallow: /"))

    def test_origins(self):
        self.assertEqual(ing.origins_for("http://www.example.org/locations/x"),
                         ["https://www.example.org", "https://example.org"])
        self.assertEqual(ing.origins_for("https://health.example.org/"),
                         ["https://health.example.org", "https://www.health.example.org",
                          "https://www.example.org", "https://example.org"])

    def test_strict_location_match(self):
        from price_contract import StrictHospitalMatcher

        m = StrictHospitalMatcher([HOSPITAL, OTHER])
        self.assertTrue(ing.strict_match(m, HOSPITAL, "West Mercy Hospital")[0])
        self.assertFalse(ing.strict_match(m, HOSPITAL, "West Mercy Surgical Center")[0])
        self.assertFalse(ing.strict_match(m, HOSPITAL, "East Mercy Hospital")[0])

    def test_system_level_name_never_matches_by_name(self):
        # "X Health System" may be a system-wide file covering several hospitals.
        from price_contract import StrictHospitalMatcher

        m = StrictHospitalMatcher([HOSPITAL, OTHER])
        for name in ("West Mercy Health System", "West Mercy Network", "West Mercy Health Partners"):
            self.assertFalse(ing.strict_match(m, HOSPITAL, name)[0], name)
        # an explicit CCN still attaches it
        self.assertEqual(m.match(["West Mercy Health System"], "CA", {"Fullerton"}, set(), ccn="990001")[1], "ccn")


class CsvParserTests(unittest.TestCase):
    def test_tall_groups_payers_and_filters_codes(self):
        meta, lines, layout = iter_mrf(FIX / "v2_tall.csv", KEEP)
        self.assertEqual(layout, "csv-tall")
        self.assertEqual(meta["last_updated_on"], "2026-03-01")
        self.assertEqual(meta["location_name"], "West Mercy Hospital")
        self.assertEqual(meta["license_state"], "CA")
        d = by_desc(lines)
        # 99213 and MS-DRG 470 are not in procedures.json: not kept.
        self.assertNotIn("Office visit", d)
        self.assertNotIn("Major joint replacement", d)
        colo = d["Colonoscopy diagnostic"]
        self.assertEqual(colo["all_codes"], "CPT:45378 | RC:750")
        self.assertEqual((colo["cash"], colo["gross"]), (1200.0, 2400.0))
        self.assertEqual(sorted(r["dollar"] for r in colo["rates"]), [900.0, 1100.0])  # percent-only row has no dollar
        self.assertEqual(len(d["Cesarean section w/o sterilization w/o CC/MCC"]["rates"]), 2)
        self.assertEqual(d["Colonoscopy with modifier"]["modifiers"], "PT")
        self.assertIn("Colonoscopy suffix code", d)  # kept so the contract can quarantine it

    def test_wide_v3_spaced_pipes(self):
        meta, lines, layout = iter_mrf(FIX / "v3_wide.csv", KEEP)
        self.assertEqual(layout, "csv-wide")
        self.assertEqual(meta["last_updated_on"], "4/1/2026")
        self.assertEqual(meta["version"], "3.0.0")
        d = by_desc(lines)
        self.assertNotIn("Unrelated item", d)
        mri = d["MRI brain without contrast"]
        self.assertEqual(mri["all_codes"], "RC:611 | CPT:70551")
        self.assertEqual(mri["billing_class"], "facility")
        self.assertEqual({(r["payer"], r["plan"], r["dollar"]) for r in mri["rates"]},
                         {("Platform Health", "PPO", 400.0), ("Region Health", "HMO", 250.0)})
        self.assertIsNone(d["MRI brain no billing class"]["billing_class"])
        self.assertEqual([r["payer"] for r in d["Colonoscopy"]["rates"]], ["Platform Health"])

    def test_gzip_and_zip_match_plain(self):
        plain = iter_mrf(FIX / "v2_tall.csv", KEEP)
        with tempfile.TemporaryDirectory() as tmp:
            gz = Path(tmp) / "mrf.csv.gz"
            gz.write_bytes(gzip.compress((FIX / "v2_tall.csv").read_bytes()))
            zp = Path(tmp) / "mrf.zip"
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("README.txt", "notes")
                z.write(FIX / "v2_tall.csv", "standardcharges.csv")
            self.assertEqual(iter_mrf(gz, KEEP), plain)
            self.assertEqual(iter_mrf(zp, KEEP), plain)

    def test_html_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.csv"
            p.write_text("<!DOCTYPE html><html>Access denied</html>", encoding="utf-8")
            with self.assertRaises(UnsupportedFormat):
                iter_mrf(p, KEEP)


class JsonParserTests(unittest.TestCase):
    def test_v2_json(self):
        meta, lines, layout = iter_mrf(FIX / "v2.json", KEEP)
        self.assertEqual(layout, "json")
        self.assertEqual(meta["last_updated_on"], "2026-02-15")
        self.assertEqual(meta["location_name"], "West Mercy Hospital")
        self.assertEqual(meta["license_number"], "50056")
        self.assertEqual(len(lines), 3)  # 2 colonoscopy charge rows + cesarean; LOCAL item dropped
        colo = [ln for ln in lines if ln["description"] == "Colonoscopy"]
        self.assertEqual([ln["modifiers"] for ln in colo], [None, "PT"])
        self.assertEqual([r["dollar"] for r in colo[0]["rates"]], [900.0])

    def test_metadata_after_items_and_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            gz = Path(tmp) / "mrf.json.gz"
            gz.write_bytes(gzip.compress((FIX / "v3_meta_last.json").read_bytes()))
            meta, lines, layout = iter_mrf(gz, KEEP)
        self.assertEqual(meta["last_updated_on"], "2026-04-01")
        self.assertEqual(meta["location_name"], "West Mercy Hospital|West Mercy Surgical Center")
        self.assertEqual(lines[0]["all_codes"], "CPT:70551")


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _extract(self, fixture: str, url: str, location: str = "West Mercy Hospital",
                 retrieved: str = "2026-05-01T12:00:00Z") -> Path:
        src = {"ccn": HOSPITAL["cmsProviderId"], "mrfUrl": url,
               "cmsHptUrl": "https://www.westmercy.example/cms-hpt.txt", "sourcePageUrl": None,
               "locationName": location, "hospitalMatch": "name+city", "retrievedAt": retrieved}
        raw = ing.build_extract(FIX / fixture, CODES, src, {"sha256": "ab" * 32, "bytes": 1})
        path = self.tmp / f"{HOSPITAL['cmsProviderId']}-{ing.url_hash(url)}.json.gz"
        ing.save_extract(path, raw)
        return path

    def test_rows_follow_contract_and_rebuild_is_identical(self):
        self._extract("v2_tall.csv", "https://www.westmercy.example/mrf/a.csv")
        self._extract("v2.json", "https://www.westmercy.example/mrf/b.json")
        self._extract("v3_wide.csv", "https://www.westmercy.example/mrf/c.csv")
        hospitals = [HOSPITAL, OTHER]
        rows, meta, q = ing.assemble(self.tmp, CODES, hospitals)
        rows2, meta2, q2 = ing.assemble(self.tmp, CODES, hospitals)
        self.assertEqual(dump_json(rows), dump_json(rows2))
        self.assertEqual(dump_json(meta), dump_json(meta2))
        self.assertEqual(dump_json(q.to_dict()), dump_json(q2.to_dict()))
        by_id = {h["id"]: h for h in hospitals}
        keys = [(r["hospitalId"], r["procedureId"]) for r in rows]
        self.assertEqual(keys, sorted(set(keys)))
        for r in rows:
            self.assertEqual(contract_problems(r, CODES, by_id), [], r)
            self.assertEqual(r["priceSource"], "hospital_mrf")
            self.assertTrue(r["mrfUrl"].startswith("https://"))
        got = {r["procedureId"]: r for r in rows}
        # Colonoscopy: v2 tall (2026-03-01) and v3 wide (2026-04-01) -> newest vintage wins.
        colo = got["proc-colonoscopy"]
        self.assertEqual(colo["priceVintage"], "2026-04-01")
        self.assertEqual(colo["mrfUrl"], "https://www.westmercy.example/mrf/c.csv")
        self.assertEqual((colo["cashMedian"], colo["grossCharge"], colo["negotiatedMedian"]), (1200, 2400, 900))
        # Cesarean: tall (2026-03-01, 2 plans) beats JSON (2026-02-15).
        ces = got["proc-cesarean"]
        self.assertEqual((ces["negotiatedLow"], ces["negotiatedHigh"], ces["payerCount"]), (12000, 14000, 2))
        self.assertIsNone(ces["cashMedian"])  # gross is never copied into cash
        self.assertEqual(ces["matchedCodes"], ["MS-DRG:788"])
        mri = got["proc-mri-brain"]
        self.assertEqual((mri["cashMedian"], mri["negotiatedLow"], mri["negotiatedHigh"]), (1080, 250, 400))
        self.assertEqual(mri["priceVintage"], "2026-04-01")
        self.assertEqual(meta["referenceDate"], "2026-05-01")
        for reason in ("line:has_modifier", "line:code_with_modifier_or_suffix", "line:billing_class_missing",
                       "row:duplicate_superseded"):
            self.assertIn(reason, q.counts, reason)

    def test_other_campus_and_future_vintage_are_quarantined(self):
        self._extract("v2_tall.csv", "https://www.westmercy.example/mrf/a.csv", location="West Mercy Surgical Center")
        self._extract("v3_wide.csv", "https://www.westmercy.example/mrf/c.csv", retrieved="2026-03-15T00:00:00Z")
        rows, _meta, q = ing.assemble(self.tmp, CODES, [HOSPITAL, OTHER])
        self.assertEqual(rows, [])
        self.assertIn("file:cms_hpt_location_no_longer_matches", q.counts)
        self.assertIn("row:vintage_after_retrieval", q.counts)

    def test_stale_codes_key_is_refused(self):
        p = self._extract("v2.json", "https://www.westmercy.example/mrf/b.json")
        raw = json.loads(gzip.decompress(p.read_bytes()))
        raw["codesKey"] = "something-else"
        p.write_bytes(gzip.compress(json.dumps(raw).encode()))
        rows, _meta, q = ing.assemble(self.tmp, CODES, [HOSPITAL])
        self.assertEqual(rows, [])
        self.assertIn("file:extract_unusable_needs_redownload", q.counts)


class ProgressTests(unittest.TestCase):
    def test_advance_never_skips_pending(self):
        order = ["A", "B", "C", "D"]
        prog = {"nextIndex": 0, "done": {"A": {}, "C": {}}, "failed": {}}
        ing.advance(prog, order)
        self.assertEqual(prog["nextIndex"], 1)  # B pending: stop there even though C is done
        prog["failed"]["B"] = "no_cms_hpt_txt"
        ing.advance(prog, order)
        self.assertEqual(prog["nextIndex"], 3)


if __name__ == "__main__":
    unittest.main()
