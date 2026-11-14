import json
import shutil
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from processing.nisar_flood import gunw_chain, synthetic
from processing.nisar_flood.constants import STUDY_BBOX
from processing.p3.ingestion import ingest
from processing.p3.phase import convert
from processing.p3.series import build_series

DATES = ["2026-06-28", "2026-07-10", "2026-07-22"]


def pair_row(ref, sec, title):
    return {"title": title, "referenceDate": ref, "secondaryDate": sec, "referenceTime": f"{ref}T10:24:00Z",
            "secondaryTime": f"{sec}T10:24:00Z", "track": 32, "direction": "D", "frame": 81, "productVersion": "1.0.11",
            "collectionShortName": "NISAR_L2_GUNW_PROVISIONAL_V1", "maturity": "provisional", "frequencyAPolarizations": ["HH"],
            "bboxCoverageFraction": 1.0, "pairDays": 12, "sizeBytes": 1, "url": "https://example.invalid/x.h5", "md5": None}


def write_gunw(path, rate_rad_per_day, days):
    """A tiny GUNW-like file: a coherent, connected, smooth ramp whose phase scales with the pair length."""
    paths = gunw_chain.gunw_paths()
    x, y = synthetic.make_axes(STUDY_BBOX, spacing=400.0, pad_m=1500.0)
    rows, cols = np.mgrid[0:y.size, 0:x.size]
    phase = (rate_rad_per_day * days) * (cols / cols.max())
    with h5py.File(path, "w") as f:
        for key, data, units in (("phase", phase, "radians"), ("coherence", np.full(phase.shape, 0.9), "unitless"),
                                 ("components", np.ones(phase.shape), "unitless")):
            ds = f.create_dataset(paths[key].strip("/"), data=data.astype("float32"))
            ds.attrs["units"] = units
        f.create_dataset(paths["x"].strip("/"), data=x)
        f.create_dataset(paths["y"].strip("/"), data=y)
        proj = f.create_dataset(paths["projection"].strip("/"), data=np.int32(32651))
        proj.attrs["epsg_code"] = np.int32(32651)


class GunwChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.raw = self.dir / "raw"
        self.raw.mkdir()
        self.rows = [pair_row(DATES[0], DATES[1], "FAKE_GUNW_A"), pair_row(DATES[1], DATES[2], "FAKE_GUNW_B")]
        for row in self.rows:
            write_gunw(self.raw / gunw_chain.local_name(row), 0.05, 12)
        self.manifest = {"gunw": self.rows, "selection": {"track": 32, "direction": "D", "frame": 81, "mode": "4005"}, "gunwChainGaps": []}
        self.paths = gunw_chain.gunw_paths()

    def tearDown(self):
        self.tmp.cleanup()

    def test_wavelength_is_l_band(self):
        self.assertAlmostEqual(gunw_chain.WAVELENGTH_M, 0.2384, places=4)

    def test_placeholders_block_everything_and_ingest_refuses(self):
        summary = gunw_chain.write_chain(self.manifest, self.dir / "chain", self.raw, paths=self.paths)
        problems = gunw_chain.blocking_problems(summary)
        self.assertTrue(any("reference area" in p for p in problems))
        self.assertTrue(any("phaseToAwaySign" in p for p in problems))
        self.assertTrue(any("sha256" in p for p in problems))
        with self.assertRaisesRegex(ValueError, "phaseToAwaySign"):
            ingest(gunw_chain.EVENT, self.dir / "chain" / summary["ingestConfigs"][0], output_root=self.dir / "out")

    def test_complete_chain_runs_through_scripts_10_11_12(self):
        ref = (120.93, 14.68, 120.97, 14.72)
        summary = gunw_chain.write_chain(self.manifest, self.dir / "chain", self.raw, paths=self.paths, phase_sign=1,
                                         fill_hashes=True, reference_bbox=ref)
        self.assertEqual(gunw_chain.blocking_problems(summary), [])
        self.assertFalse(summary["referenceIsPlaceholder"])
        root = self.dir / "out"
        los = []
        for name in summary["ingestConfigs"]:
            config = json.loads((self.dir / "chain" / name).read_text())
            self.assertEqual(config["event"], "camanava_2026")
            self.assertEqual(config["source"]["acquisitionDates"][0][-1], "Z")
            self.assertIn("window", config["sourceProfile"])
            self.assertEqual(config["sourceProfile"]["crs"], "EPSG:32651")
            self.assertEqual(config["sourceProfile"]["status"], "needs-review")
            gunw_manifest = ingest(gunw_chain.EVENT, self.dir / "chain" / name, output_root=root)
            los_manifest = convert(gunw_chain.EVENT, gunw_manifest, self.dir / "chain" / summary["referenceConfig"], output_root=root)
            los.append(str(los_manifest))
        series = build_series(gunw_chain.EVENT, los, output_root=root)
        manifest = json.loads(Path(series).read_text())
        self.assertIn(manifest["dataKind"], ("observed", "derived"))  # never synthetic, never auto-published
        self.assertEqual(manifest["dataStatus"], "needs-review")

    def test_los_value_follows_wavelength_and_sign(self):
        ref = (120.93, 14.68, 120.97, 14.72)
        results = {}
        for sign in (1, -1):
            summary = gunw_chain.write_chain(self.manifest, self.dir / f"chain{sign}", self.raw, paths=self.paths, phase_sign=sign,
                                             fill_hashes=True, reference_bbox=ref, max_pairs=1)
            root = self.dir / f"out{sign}"
            gunw_manifest = ingest(gunw_chain.EVENT, self.dir / f"chain{sign}" / summary["ingestConfigs"][0], output_root=root)
            los = convert(gunw_chain.EVENT, gunw_manifest, self.dir / f"chain{sign}" / summary["referenceConfig"], output_root=root)
            manifest = json.loads(Path(los).read_text())
            results[sign] = manifest
        self.assertEqual(results[1]["phaseToAwaySign"], 1)
        self.assertEqual(results[-1]["phaseToAwaySign"], -1)
        self.assertAlmostEqual(results[1]["wavelengthMetres"], gunw_chain.WAVELENGTH_M)
        self.assertEqual(results[1]["spatialReferenceId"], "camanava-ref-t032_D_f081")

    def test_shell_script_lists_all_three_steps_with_absolute_paths(self):
        summary = gunw_chain.write_chain(self.manifest, self.dir / "chain", self.raw, paths=self.paths)
        script = (self.dir / "chain" / summary["shellScript"]).read_text()
        self.assertEqual(script.count("10_ingest_nisar.py"), 2)
        self.assertEqual(script.count("11_phase_to_los.py"), 2)
        self.assertEqual(script.count("12_motion_series.py"), 1)
        self.assertIn("set -euo pipefail", script)
        self.assertIn(str((self.dir / "chain").resolve()), script)

    def test_missing_files_are_reported_not_invented(self):
        shutil.rmtree(self.raw)
        self.raw.mkdir()
        summary = gunw_chain.write_chain(self.manifest, self.dir / "chain", self.raw, paths=self.paths, phase_sign=1)
        self.assertFalse(any(p["downloaded"] for p in summary["pairs"]))
        config = json.loads((self.dir / "chain" / summary["ingestConfigs"][0]).read_text())
        self.assertEqual(config["source"]["sha256"], gunw_chain.SHA_PLACEHOLDER)
        self.assertNotIn("window", config["sourceProfile"])

    def test_wrong_layout_is_named(self):
        with self.assertRaisesRegex(ValueError, "fix --gunw-base"):
            gunw_chain.write_chain(self.manifest, self.dir / "chain", self.raw, paths=gunw_chain.gunw_paths(pol="VV"), fill_hashes=True)

    def test_manifest_without_pairs_is_refused(self):
        with self.assertRaises(ValueError):
            gunw_chain.write_chain({"gunw": [], "selection": self.manifest["selection"]}, self.dir / "c", self.raw, paths=self.paths)


if __name__ == "__main__":
    unittest.main()
