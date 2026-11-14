"""Grid geometry: study-bbox -> projected window, pixel areas, lon/lat <-> row/col.

A ``Grid`` has the same dict form as ``processing.p3.core`` (crs, 6-number
affine transform, width, height) so products line up with the P3 modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from affine import Affine
from pyproj import CRS, Transformer
from scipy.interpolate import RegularGridInterpolator


class OutsideGrid(ValueError):
    """The requested bbox does not overlap the product grid."""


@dataclass(frozen=True)
class Grid:
    crs: str
    transform: tuple[float, float, float, float, float, float]  # a, b, c, d, e, f (north-up: e < 0)
    width: int
    height: int

    @property
    def affine(self) -> Affine:
        return Affine(*self.transform)

    def to_dict(self) -> dict:
        return {"crs": self.crs, "transform": list(self.transform), "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, value: dict) -> "Grid":
        return cls(str(value["crs"]), tuple(float(v) for v in value["transform"][:6]), int(value["width"]), int(value["height"]))

    def same_as(self, other: "Grid") -> bool:
        return (self.crs == other.crs and self.width == other.width and self.height == other.height
                and np.allclose(self.transform, other.transform, rtol=0, atol=1e-6))

    # -- coordinate helpers -------------------------------------------------
    def _to_native(self) -> Transformer:
        return Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)

    def _to_lonlat(self) -> Transformer:
        return Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)

    def lonlat_to_rowcol(self, lon, lat) -> tuple[np.ndarray, np.ndarray]:
        """Fractional (row, col) of the pixel *containing* lon/lat (floor gives the index)."""
        x, y = self._to_native().transform(np.asarray(lon, dtype="float64"), np.asarray(lat, dtype="float64"))
        col, row = ~self.affine @ (x, y)
        return np.asarray(row), np.asarray(col)

    def rowcol_to_lonlat(self, row, col) -> tuple[np.ndarray, np.ndarray]:
        """Lon/lat of pixel centres for integer-or-float (row, col) index arrays."""
        x, y = self.affine @ (np.asarray(col, dtype="float64") + 0.5, np.asarray(row, dtype="float64") + 0.5)
        lon, lat = self._to_lonlat().transform(x, y)
        return np.asarray(lon), np.asarray(lat)

    def pixel_center_lonlat(self) -> tuple[np.ndarray, np.ndarray]:
        rows, cols = np.mgrid[0:self.height, 0:self.width]
        return self.rowcol_to_lonlat(rows, cols)

    def bounds_wgs84(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) of the grid edge, densified so rotation/convergence is included."""
        n = 25
        cols = np.concatenate([np.linspace(0, self.width, n), np.full(n, self.width), np.linspace(self.width, 0, n), np.zeros(n)])
        rows = np.concatenate([np.zeros(n), np.linspace(0, self.height, n), np.full(n, self.height), np.linspace(self.height, 0, n)])
        x, y = self.affine @ (cols, rows)
        lon, lat = self._to_lonlat().transform(x, y)
        return float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())

    def native_resolution(self) -> dict:
        crs = CRS.from_user_input(self.crs)
        dx, dy = abs(self.transform[0]), abs(self.transform[4])
        if crs.is_projected:
            fx = crs.axis_info[0].unit_conversion_factor if crs.axis_info else 1.0
            return {"x": dx * fx, "y": dy * fx, "units": "m"}
        return {"x": dx, "y": dy, "units": "degree"}


def study_mask(grid: Grid, bbox: Iterable[float]) -> np.ndarray:
    """True where the pixel centre lies inside the WGS84 bbox."""
    west, south, east, north = bbox
    lon, lat = grid.pixel_center_lonlat()
    return (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)


def pixel_area_km2(grid: Grid, lattice: int = 17) -> np.ndarray:
    """Per-pixel area in km2, computed in a Lambert azimuthal equal-area CRS centred on the grid.

    The exact area of a sample of cells is measured by projecting their four corners to the
    equal-area CRS (shoelace formula); the smooth result is interpolated to every pixel.
    This corrects the UTM scale factor (up to ~0.08 % of area) and works for geographic grids too.
    """
    west, south, east, north = grid.bounds_wgs84()
    laea = CRS.from_proj4(f"+proj=laea +lat_0={(south + north) / 2:.6f} +lon_0={(west + east) / 2:.6f} +datum=WGS84 +units=m +no_defs")
    transformer = Transformer.from_crs(grid.crs, laea, always_xy=True)
    n_r = min(lattice, grid.height)
    n_c = min(lattice, grid.width)
    rows = np.linspace(0, grid.height - 1, n_r)
    cols = np.linspace(0, grid.width - 1, n_c)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    corners = []
    for dr, dc in ((0, 0), (0, 1), (1, 1), (1, 0)):
        x, y = grid.affine @ (cc + dc, rr + dr)
        corners.append(transformer.transform(x, y))
    xs = np.stack([c[0] for c in corners])
    ys = np.stack([c[1] for c in corners])
    shoelace = 0.5 * np.abs(sum(xs[i] * ys[(i + 1) % 4] - xs[(i + 1) % 4] * ys[i] for i in range(4)))
    sample_km2 = shoelace / 1e6
    if n_r == 1 and n_c == 1:
        return np.full((grid.height, grid.width), float(sample_km2[0, 0]), dtype="float64")
    # Degenerate lattice axes (1 pixel wide/high) are padded so the interpolator has two points.
    if n_r == 1:
        sample_km2 = np.vstack([sample_km2, sample_km2]); rows = np.array([0.0, 1.0])
    if n_c == 1:
        sample_km2 = np.hstack([sample_km2, sample_km2]); cols = np.array([0.0, 1.0])
    interp = RegularGridInterpolator((rows, cols), sample_km2, method="linear", bounds_error=False, fill_value=None)
    full_r, full_c = np.mgrid[0:grid.height, 0:grid.width]
    out = interp(np.stack([full_r.ravel().astype("float64"), full_c.ravel().astype("float64")], axis=-1))
    return out.reshape(grid.height, grid.width)


def _axis_info(values: np.ndarray, name: str) -> tuple[float, bool]:
    values = np.asarray(values, dtype="float64")
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError(f"{name} coordinates must be a finite 1-D array with at least 2 values")
    diffs = np.diff(values)
    step = float(np.median(diffs))
    if step == 0 or not np.allclose(diffs, step, rtol=1e-6, atol=abs(step) * 1e-6):
        raise ValueError(f"{name} coordinates are not a regular, strictly monotonic axis")
    return step, step > 0


def window_for_bbox(x: np.ndarray, y: np.ndarray, crs: str, bbox: Iterable[float], *,
                    coordinates_are: str = "center", pad: int = 2) -> tuple[slice, slice, Grid, dict]:
    """Row/column slices of the pixels that overlap the WGS84 ``bbox`` (plus ``pad`` pixels).

    ``x``/``y`` are the full 1-D coordinate arrays of the product grid (projected metres).
    Returns (rows, cols, window_grid, info). Raises ``OutsideGrid`` when there is no overlap.
    """
    west, south, east, north = bbox
    to_native = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    t = np.linspace(0.0, 1.0, 41)
    edge_lon = np.concatenate([west + t * (east - west), np.full(41, east), east - t * (east - west), np.full(41, west)])
    edge_lat = np.concatenate([np.full(41, south), south + t * (north - south), np.full(41, north), north - t * (north - south)])
    ex, ey = to_native.transform(edge_lon, edge_lat)
    xmin, xmax, ymin, ymax = float(ex.min()), float(ex.max()), float(ey.min()), float(ey.max())

    dx, _ = _axis_info(x, "x")
    dy, _ = _axis_info(y, "y")
    half = 0.5 if coordinates_are == "center" else 0.0
    # Pixel edges: left edge of column 0 and top edge of row 0 in native coordinates.
    x0 = float(x[0]) - (half * dx if coordinates_are == "center" else 0.0)
    y0 = float(y[0]) - (half * dy if coordinates_are == "center" else 0.0)

    def span(lo: float, hi: float, origin: float, step: float, size: int) -> tuple[int, int]:
        a, b = (lo - origin) / step, (hi - origin) / step
        first, last = (a, b) if step > 0 else (b, a)
        i0 = int(np.floor(min(first, last))) - pad
        i1 = int(np.ceil(max(first, last))) + pad
        return max(i0, 0), min(i1, size)

    c0, c1 = span(xmin, xmax, x0, dx, x.size)
    r0, r1 = span(ymin, ymax, y0, dy, y.size)
    if c1 <= c0 or r1 <= r0:
        raise OutsideGrid("The study bbox does not overlap this product's grid")

    flip_x, flip_y = dx < 0, dy > 0
    if flip_x or flip_y:
        raise ValueError("Product axes are not north-up/east-right; add an explicit adapter before using this file")
    transform = (dx, 0.0, x0 + c0 * dx, 0.0, dy, y0 + r0 * dy)
    grid = Grid(crs, transform, c1 - c0, r1 - r0)
    # How much of the requested projected rectangle the product grid covers (1.0 = fully inside).
    gx_lo, gx_hi = x0, x0 + x.size * dx
    gy_hi, gy_lo = y0, y0 + y.size * dy
    ox = max(0.0, min(xmax, gx_hi) - max(xmin, gx_lo))
    oy = max(0.0, min(ymax, gy_hi) - max(ymin, gy_lo))
    covered = (ox * oy) / ((xmax - xmin) * (ymax - ymin))
    info = {"rowStart": r0, "rowStop": r1, "colStart": c0, "colStop": c1,
            "requestedRectangleCoveredByGrid": round(float(covered), 4), "padPixels": pad}
    return slice(r0, r1), slice(c0, c1), grid, info
