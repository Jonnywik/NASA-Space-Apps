"""Small helpers shared by the NISAR tests. Everything here is synthetic test data."""
import tempfile
from pathlib import Path

import h5py
import numpy as np
from pyproj import Transformer

from processing.nisar_flood import gcov, pipeline, synthetic
from processing.nisar_flood.constants import DEFAULT_LAYOUT, STUDY_BBOX

EPSG = 32651


def write_gcov(path, hh_power, hv_power, x, y, *, epsg=EPSG, layout=DEFAULT_LAYOUT, fill=np.nan, crs_attr=True, units=None):
    """A minimal GCOV-like HDF5 with the expected layout and arrays given as linear power."""
    with h5py.File(path, "w") as handle:
        group = handle.create_group(layout.base.strip("/"))
        for name, data in ((layout.hh, hh_power), (layout.hv, hv_power)):
            ds = group.create_dataset(name, data=np.asarray(data, dtype="float32"), chunks=(32, 32))
            if fill is not None:
                ds.attrs["_FillValue"] = np.float32(fill)
            if units:
                ds.attrs["units"] = units
        group.create_dataset(layout.x, data=np.asarray(x, dtype="float64"))
        group.create_dataset(layout.y, data=np.asarray(y, dtype="float64"))
        proj = group.create_dataset(layout.projection, data=np.int32(epsg))
        if crs_attr:
            proj.attrs["epsg_code"] = np.int32(epsg)
    return Path(path)


def bbox_axes(spacing=500.0, pad_m=1500.0):
    return synthetic.make_axes(STUDY_BBOX, spacing=spacing, pad_m=pad_m, epsg=EPSG)


def passes_from_levels(directory, levels, *, spacing=300.0, nodata_pass=None):
    """Write one synthetic GCOV per level, read them back through the real reader, return PassInput list."""
    out = []
    for i, level in enumerate(levels):
        block = (120.97, 14.66, 121.04, 14.72) if i == nodata_pass else None
        path = synthetic.write_synthetic_gcov(Path(directory) / f"f{i}.h5", level=level, seed=i, nodata_block=block, spacing=spacing)
        window, info = gcov.read_window_from_source(str(path), speckle_window=1)
        day = f"2026-07-{i + 1:02d}"
        out.append(pipeline.PassInput(day.replace("-", ""), day, f"{day}T10:30:00Z", f"SYNTHETIC-FIXTURE-{day}", "synthetic", window,
                                      source={"title": f"SYNTHETIC-FIXTURE-{day}", "access": info}))
    return out


def build_product(directory, *, data_kind="synthetic", levels=(0.05, 0.3, 0.2, 0.5), spacing=300.0, nodata_pass=2):
    """Run the whole chain on tiny synthetic GCOV files; returns (output_root, out_dir, analysis)."""
    directory = Path(directory)
    passes = passes_from_levels(directory / "fixtures", levels, spacing=spacing, nodata_pass=nodata_pass)
    analysis = pipeline.analyse(passes, calibrate=True, min_valid_passes=2, log=lambda *a: None)
    root = directory / "output"
    out_dir = root / "camanava_2026" / "nisar"
    pipeline.export_product(analysis, out_dir, data_kind=data_kind,
                            source={"name": "test fixture", "url": None, "version": "test"},
                            track={"track": 133, "direction": "D", "frame": 81, "mode": "4005"})
    return root, out_dir, analysis
