import http.server
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np

from processing.nisar_flood import gcov, remote
from processing.nisar_flood.constants import STUDY_BBOX, GcovLayout
from processing.nisar_flood.geo import OutsideGrid
from nisar_fixtures import EPSG, bbox_axes, write_gcov


def scene(x, y):
    """Linear power with a recognisable pattern: HH = column index based, HV = row index based."""
    cols = np.arange(x.size, dtype="float32")[None, :] + 1.0
    rows = np.arange(y.size, dtype="float32")[:, None] + 1.0
    return (cols + 0 * rows) * 1e-3, (rows + 0 * cols) * 1e-4


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.x, self.y = bbox_axes()

    def tearDown(self):
        self.tmp.cleanup()

    def test_window_values_match_source_pixels(self):
        hh, hv = scene(self.x, self.y)
        path = write_gcov(self.dir / "a.h5", hh, hv, self.x, self.y)
        w, info = gcov.read_window_from_source(str(path), speckle_window=1)
        r0, c0 = w.meta["window"]["rowStart"], w.meta["window"]["colStart"]
        pad = 2
        self.assertEqual(info["mode"], "local")
        # dB of the source pixel at the window's first row/column
        np.testing.assert_allclose(w.hh_db[0, 0], 10 * np.log10(hh[r0, c0]), rtol=1e-5)
        np.testing.assert_allclose(w.hv_db[3, 7], 10 * np.log10(hv[r0 + 3, c0 + 7]), rtol=1e-5)
        self.assertEqual(w.hh_db.shape, (w.grid.height, w.grid.width))
        self.assertLess(w.grid.width, self.x.size)
        # the grid origin is the pixel EDGE (centre minus half a pixel) of the first pixel read
        self.assertAlmostEqual(w.grid.transform[2], self.x[c0] - 250.0)
        self.assertAlmostEqual(w.grid.transform[5], self.y[r0] + 250.0)
        self.assertEqual(w.grid.crs, f"EPSG:{EPSG}")

    def test_nodata_zero_negative_and_fill_value_are_nan_not_numbers(self):
        from processing.nisar_flood.geo import window_for_bbox
        rows, cols, _, _ = window_for_bbox(self.x, self.y, f"EPSG:{EPSG}", STUDY_BBOX, pad=4)
        hh, hv = scene(self.x, self.y)
        r, c = rows.start + 10, cols.start + 10
        hh[r:r + 3, c:c + 3] = np.nan          # NaN block
        hh[r + 5, c + 5] = 0.0                  # zero power
        hv[r + 6, c + 6] = -1.0                 # negative power
        hh[r + 7, c + 7] = -9999.0              # file's declared fill value
        path = write_gcov(self.dir / "b.h5", hh, hv, self.x, self.y, fill=-9999.0)
        w, _ = gcov.read_window_from_source(str(path), speckle_window=1)
        r0, c0 = w.meta["window"]["rowStart"], w.meta["window"]["colStart"]
        for (rr, cc), arr in (((r + 1, c + 1), w.hh_db), ((r + 5, c + 5), w.hh_db), ((r + 6, c + 6), w.hv_db), ((r + 7, c + 7), w.hh_db)):
            self.assertTrue(np.isnan(arr[rr - r0, cc - c0]), (rr, cc))
        # neighbours of the defects are still real dB numbers
        self.assertTrue(np.isfinite(w.hh_db[r + 9 - r0, c + 9 - c0]))
        self.assertTrue(np.isfinite(w.hv_db[r + 5 - r0, c + 5 - c0]))

    def test_power_to_db(self):
        db = gcov.power_to_db(np.array([1.0, 0.1, 0.01, 0.0, -1.0, np.nan, np.inf]))
        np.testing.assert_allclose(db[:3], [0.0, -10.0, -20.0], atol=1e-5)
        self.assertTrue(np.all(np.isnan(db[3:])))

    def test_speckle_filter_ignores_nodata_and_keeps_it_nodata(self):
        p = np.full((9, 9), 0.01, dtype="float32")
        p[4, 4] = np.nan
        out = gcov.boxcar_power(p, 3)
        self.assertTrue(np.isnan(out[4, 4]))
        np.testing.assert_allclose(out[3, 3], 0.01, rtol=1e-5)  # a NaN neighbour does not pull the mean down
        np.testing.assert_allclose(out[0, 0], 0.01, rtol=1e-5)  # edges are not biased low by zero padding

    def test_missing_dataset_error_names_the_path(self):
        hh, hv = scene(self.x, self.y)
        path = write_gcov(self.dir / "c.h5", hh, hv, self.x, self.y)
        with self.assertRaisesRegex(gcov.LayoutError, "HVHV_WRONG|not in this file"):
            gcov.read_window_from_source(str(path), layout=GcovLayout(hv="HVHV_WRONG"))

    def test_db_units_are_refused(self):
        hh, hv = scene(self.x, self.y)
        path = write_gcov(self.dir / "d.h5", hh, hv, self.x, self.y, units="dB")
        with self.assertRaisesRegex(gcov.LayoutError, "already in dB"):
            gcov.read_window_from_source(str(path))

    def test_crs_is_read_from_file_never_assumed(self):
        hh, hv = scene(self.x, self.y)
        path = write_gcov(self.dir / "e.h5", hh, hv, self.x, self.y, crs_attr=False)
        # scalar projection dataset still carries the code as its value
        w, _ = gcov.read_window_from_source(str(path))
        self.assertIn("32651", w.grid.crs)
        import h5py
        with h5py.File(path, "r+") as f:
            del f[DEFAULT_PROJECTION]
            f.create_dataset(DEFAULT_PROJECTION, data=np.int32(0))
        with self.assertRaisesRegex(gcov.LayoutError, "Cannot determine the grid CRS"):
            gcov.read_window_from_source(str(path))
        w, _ = gcov.read_window_from_source(str(path), layout=GcovLayout(crs_fallback="EPSG:32651"))
        self.assertEqual(w.grid.crs, "EPSG:32651")

    def test_bbox_outside_the_product(self):
        x = np.arange(500000.0, 520000.0, 500.0) + 250
        y = np.arange(1600000.0, 1580000.0, -500.0) - 250
        hh, hv = scene(x, y)
        path = write_gcov(self.dir / "f.h5", hh, hv, x, y)
        with self.assertRaises(OutsideGrid):
            gcov.read_window_from_source(str(path))

    def test_local_file_missing(self):
        with self.assertRaises(FileNotFoundError):
            gcov.read_window_from_source(str(self.dir / "nope.h5"))

    def test_url_without_token_is_refused_without_network(self):
        with self.assertRaises(remote.AuthError):
            gcov.read_window_from_source("https://example.invalid/x.h5", token=None)


DEFAULT_PROJECTION = "/science/LSAR/GCOV/grids/frequencyA/projection"


class _Handler(http.server.BaseHTTPRequestHandler):
    """Tiny file server with Range support. mode 'origin' redirects (after checking the token); 'storage' serves bytes."""
    log_requests = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        auth = self.headers.get("Authorization")
        type(self).log_requests.append((self.server.role, self.path, auth))
        if self.server.role == "origin":
            if auth != "Bearer test-token":
                self.send_response(401); self.end_headers(); return
            self.send_response(307)
            self.send_header("Location", f"http://localhost:{self.server.storage_port}/blob?X-Signature=secret")
            self.end_headers()
            return
        if auth is not None:  # pre-signed storage must never receive the token
            self.send_response(400); self.end_headers(); return
        data = self.server.payload
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            start, _, stop = rng[6:].partition("-")
            start = int(start); stop = int(stop) if stop else len(data) - 1
            chunk = data[start:stop + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{start + len(chunk) - 1}/{len(data)}")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


def _serve(role, payload=b"", storage_port=None):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.role, server.payload, server.storage_port = role, payload, storage_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class RemoteReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        x, y = bbox_axes()
        hh, hv = scene(x, y)
        self.path = write_gcov(self.dir / "r.h5", hh, hv, x, y)
        self.payload = self.path.read_bytes()
        _Handler.log_requests = []
        self.storage = _serve("storage", self.payload)
        self.origin = _serve("origin", storage_port=self.storage.server_address[1])
        self.url = f"http://127.0.0.1:{self.origin.server_address[1]}/file.h5"

    def tearDown(self):
        self.origin.shutdown(); self.storage.shutdown()
        self.origin.server_close(); self.storage.server_close()
        self.tmp.cleanup()

    def test_range_read_follows_redirect_and_drops_token_off_nasa_hosts(self):
        stream = remote.HttpRangeFile(self.url, "test-token", block_size=64 * 1024)
        self.assertEqual(stream.size, len(self.payload))
        stream.seek(0)
        self.assertEqual(stream.read(8), self.payload[:8])
        stream.seek(1000); self.assertEqual(stream.read(5000), self.payload[1000:6000])
        roles = {(role, auth) for role, _, auth in _Handler.log_requests}
        self.assertIn(("origin", "Bearer test-token"), roles)
        self.assertTrue(all(auth is None for role, _, auth in _Handler.log_requests if role == "storage"))
        stream.close()

    def test_bad_token_is_a_clear_auth_error_without_leaking_it(self):
        with self.assertRaises(remote.AuthError) as ctx:
            remote.HttpRangeFile(self.url, "wrong-token")
        self.assertNotIn("wrong-token", str(ctx.exception))

    def test_windowed_hdf5_read_over_http_matches_local_and_fetches_little(self):
        local, _ = gcov.read_window_from_source(str(self.path), speckle_window=1)
        remote_window, info = gcov.read_window_from_source(self.url, token="test-token", speckle_window=1)
        self.assertEqual(info["mode"], "remote-range")
        np.testing.assert_array_equal(np.nan_to_num(local.hh_db, nan=-999), np.nan_to_num(remote_window.hh_db, nan=-999))
        self.assertLessEqual(info["bytesFetched"], len(self.payload) * 4)  # block cache keeps re-reads in check
        self.assertNotIn("test-token", str(info))
        self.assertNotIn("X-Signature", str(info))

    def test_full_download_fallback_verifies_size_and_md5(self):
        import hashlib
        md5 = hashlib.md5(self.payload).hexdigest()
        path = remote.download(self.url, self.dir / "dl", "test-token", expected_md5=md5, expected_size=len(self.payload))
        self.assertEqual(path.read_bytes(), self.payload)
        (self.dir / "dl2").mkdir()
        with self.assertRaises(remote.RemoteError):
            remote.download(self.url, self.dir / "dl2", "test-token", expected_md5="0" * 32)
        self.assertEqual(list((self.dir / "dl2").iterdir()), [])  # corrupt file removed

    def test_redact_hides_presigned_query(self):
        self.assertEqual(remote._redact("https://h/x.h5?X-Amz-Signature=abc"), "https://h/x.h5")

    def test_token_only_from_environment(self):
        self.assertIsNone(remote.get_token({}))
        self.assertEqual(remote.get_token({"EARTHDATA_TOKEN": " abc "}), "abc")


if __name__ == "__main__":
    unittest.main()
