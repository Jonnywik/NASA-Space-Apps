import json
import unittest
from pathlib import Path

from processing.nisar_flood import cmr
from processing.nisar_flood.constants import STUDY_BBOX

GCOV_TITLE = "NISAR_L2_PR_GCOV_024_032_D_081_4005_DHDH_A_20260628T102400_20260628T102435_P05023_N_F_J_001"
GCOV_P = "NISAR_L2_PR_GCOV_023_133_D_081_4005_DHDH_A_20260623T103220_20260623T103243_P05023_N_P_J_001"
GUNW_TITLE = ("NISAR_L2_PR_GUNW_024_032_D_081_025_4000_SH_20260628T102400_20260628T102435_"
              "20260710T102400_20260710T102434_P05023_N_F_J_001")
FULL = [(120.0, 14.0), (122.0, 14.0), (122.0, 15.5), (120.0, 15.5), (120.0, 14.0)]
WEST_THIRD = [(120.0, 14.0), (120.91, 14.0), (120.91, 15.5), (120.0, 15.5), (120.0, 14.0)]


def item(title, start, points, *, track, direction, frame, full=True, size=5_000_000_000, version="1.0.11"):
    return {"meta": {"concept-id": "G1-ASF"}, "umm": {
        "GranuleUR": title,
        "TemporalExtent": {"RangeDateTime": {"BeginningDateTime": start}},
        "AdditionalAttributes": [
            {"Name": "TRACK_NUMBER", "Values": [str(track)]}, {"Name": "ASCENDING_DESCENDING", "Values": ["DESCENDING" if direction == "D" else "ASCENDING"]},
            {"Name": "FRAME_NUMBER", "Values": [str(frame)]}, {"Name": "FULL_FRAME", "Values": ["TRUE" if full else "FALSE"]},
            {"Name": "PRODUCT_VERSION", "Values": [version]}, {"Name": "FREQUENCY_A_POLARIZATION", "Values": ["HH", "HV"]},
            {"Name": "RANGE_BANDWIDTH_CONCAT", "Values": ["40+5"]}],
        "SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": {"GPolygons": [{"Boundary": {"Points": [
            {"Longitude": x, "Latitude": y} for x, y in points]}}]}}},
        "DataGranule": {"ArchiveAndDistributionInformation": [
            {"Name": f"{title}.h5", "SizeInBytes": size, "Checksum": {"Value": "abc123", "Algorithm": "MD5"}},
            {"Name": f"{title}_QA_STATS.h5", "SizeInBytes": 70000}]},
        "RelatedUrls": [{"URL": f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/X/{title}/{title}.h5", "Type": "GET DATA"},
                        {"URL": f"s3://bucket/{title}.h5", "Type": "GET DATA VIA DIRECT ACCESS"}]}}


class ParseTests(unittest.TestCase):
    def test_gcov_row_fields(self):
        row = cmr.parse_granule(item(GCOV_TITLE, "2026-06-28T10:24:00.000000Z", FULL, track=32, direction="D", frame=81),
                                "C2854338529-ASF", "GCOV", STUDY_BBOX)
        self.assertEqual((row["track"], row["direction"], row["frame"], row["mode"]), (32, "D", 81, "4005"))
        self.assertEqual(row["date"], "2026-06-28")
        self.assertEqual(row["acquisitionTime"], "2026-06-28T10:24:00Z")
        self.assertEqual(row["acquisitionTimeManila"], "2026-06-28T18:24:00+08:00")
        self.assertEqual(row["maturity"], "provisional")
        self.assertEqual(row["collectionShortName"], "NISAR_L2_GCOV_PROVISIONAL_V1")
        self.assertEqual(row["sizeBytes"], 5_000_000_000)
        self.assertEqual(row["md5"], "abc123")
        self.assertTrue(row["url"].startswith("https://nisar.asf.earthdatacloud.nasa.gov/"))
        self.assertEqual(row["bboxCoverageFraction"], 1.0)
        self.assertTrue(row["fullFrame"])

    def test_ascending_pass_keeps_utc_date_and_local_next_day(self):
        title = GCOV_TITLE.replace("032_D", "140_A").replace("20260628T102400", "20260623T213035")
        row = cmr.parse_granule(item(title, "2026-06-23T21:30:35.000000Z", FULL, track=140, direction="A", frame=9),
                                "C2854338529-ASF", "GCOV", STUDY_BBOX)
        self.assertEqual(row["date"], "2026-06-23")
        self.assertTrue(row["acquisitionTimeManila"].startswith("2026-06-24T05:30:35"))

    def test_footprint_coverage_fraction(self):
        row = cmr.parse_granule(item(GCOV_P, "2026-06-23T10:32:20.000000Z", WEST_THIRD, track=133, direction="D", frame=81, full=False),
                                "C2854338529-ASF", "GCOV", STUDY_BBOX)
        # bbox is 120.88..121.04; footprint reaches 120.91 -> (0.03 / 0.16)
        self.assertAlmostEqual(row["bboxCoverageFraction"], 0.1875, places=3)
        self.assertFalse(row["fullFrame"])

    def test_gunw_pair_fields(self):
        row = cmr.parse_granule(item(GUNW_TITLE, "2026-06-28T10:24:00.000000Z", FULL, track=32, direction="D", frame=81),
                                "C2854335566-ASF", "GUNW", STUDY_BBOX)
        self.assertEqual((row["referenceDate"], row["secondaryDate"], row["pairDays"]), ("2026-06-28", "2026-07-10", 12))
        self.assertEqual(row["referenceTime"], "2026-06-28T10:24:00Z")
        self.assertEqual(row["secondaryTime"], "2026-07-10T10:24:00Z")
        self.assertEqual(row["mode"], "4000")

    def test_unknown_title_pattern_is_skipped(self):
        self.assertIsNone(cmr.parse_granule(item("SOMETHING_ELSE", "2026-06-28T10:24:00Z", FULL, track=1, direction="D", frame=1),
                                             "C2854338529-ASF", "GCOV", STUDY_BBOX))


class SelectionTests(unittest.TestCase):
    def rows(self):
        a = cmr.parse_granule(item(GCOV_TITLE, "2026-06-28T10:24:00.000000Z", FULL, track=32, direction="D", frame=81), "C2854338529-ASF", "GCOV", STUDY_BBOX)
        dup = dict(a, collection="C3622241360-ASF", collectionShortName="NISAR_L2_GCOV_V1", maturity="v1")
        other_mode = dict(a, mode="2005", date="2026-06-29")
        other_track = dict(a, track=39, direction="A", frame=9)
        return [a, dup, other_mode, other_track]

    def test_filters_and_prefers_v1_for_same_date(self):
        chosen, notes = cmr.select_gcov(self.rows(), 32, "D", 81, "4005")
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["maturity"], "v1")
        self.assertEqual(len(notes), 1)

    def test_gunw_mode_mapping_and_chain_gaps(self):
        self.assertEqual(cmr.gunw_mode_for("4005"), "4000")
        self.assertEqual(cmr.gunw_mode_for("2005"), "2000")
        pairs = [{"referenceDate": "2026-06-28", "secondaryDate": "2026-07-10"},
                 {"referenceDate": "2026-07-10", "secondaryDate": "2026-07-22"},
                 {"referenceDate": "2026-08-15", "secondaryDate": "2026-08-27"}]
        self.assertEqual(cmr.pair_chain_gaps(pairs), [{"after": "2026-07-22", "next": "2026-08-15"}])

    def test_manifest_warns_on_low_coverage_and_partial_frames(self):
        row = cmr.parse_granule(item(GCOV_P, "2026-06-23T10:32:20.000000Z", WEST_THIRD, track=133, direction="D", frame=81, full=False),
                                "C2854338529-ASF", "GCOV", STUDY_BBOX)
        manifest = cmr.build_manifest(STUDY_BBOX, {"rows": {"GCOV": [row], "GUNW": []}, "requests": {}},
                                      track=133, direction="D", frame=81, mode="4005")
        text = " ".join(manifest["warnings"])
        self.assertIn("cover only", text)
        self.assertIn("partial frames", text)
        self.assertEqual(manifest["selection"]["gcovDates"], ["2026-06-23"])
        self.assertEqual(manifest["trackSummary"][0]["track"], 133)

    def test_empty_selection_says_so(self):
        manifest = cmr.build_manifest(STUDY_BBOX, {"rows": {"GCOV": [], "GUNW": []}, "requests": {}}, track=1, direction="D", frame=1, mode=None)
        self.assertTrue(any("No GCOV granules" in w for w in manifest["warnings"]))

    def test_paging_and_search_over_canned_responses(self):
        pages = {1: {"hits": 3, "items": [item(GCOV_TITLE, "2026-06-28T10:24:00Z", FULL, track=32, direction="D", frame=81)] * 2},
                 2: {"hits": 3, "items": [item(GCOV_TITLE, "2026-07-10T10:24:00Z", FULL, track=32, direction="D", frame=81)]}}
        def fetch(url):
            if "C2854338529-ASF" not in url:
                return {"hits": 0, "items": []}
            page = int(url.split("page_num=")[1].split("&")[0])
            return pages[page]
        found = cmr.search(STUDY_BBOX, fetch_json=fetch)
        self.assertEqual(len(found["rows"]["GCOV"]), 3)


class RealManifestTests(unittest.TestCase):
    """The committed manifests are real CMR output; check they are internally consistent."""
    def test_committed_manifests(self):
        folder = Path(__file__).resolve().parents[1] / "data" / "cache" / "nisar"
        files = sorted(folder.glob("nisar_manifest_*.json"))
        self.assertTrue(files, "run scripts/19_nisar_search.py")
        for path in files:
            m = json.loads(path.read_text())
            self.assertEqual(m["dataKind"], "observed")
            dates = [r["date"] for r in m["gcov"]]
            self.assertEqual(dates, sorted(set(dates)))
            for r in m["gcov"]:
                self.assertTrue(r["url"].startswith("https://nisar.asf.earthdatacloud.nasa.gov/"))
                self.assertIn(r["title"], r["url"])
                self.assertEqual(r["track"], m["selection"]["track"])


if __name__ == "__main__":
    unittest.main()
