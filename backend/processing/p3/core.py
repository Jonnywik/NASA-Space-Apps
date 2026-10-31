"""Shared, immutable product publication and raster I/O."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
import numpy as np
import rasterio
from affine import Affine

OUTPUT_ROOT = Path(__file__).resolve().parents[2] / 'data' / 'output'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_name(value):
    if not isinstance(value, str) or not value or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in value):
        raise ValueError('Invalid event, product or run identifier')
    return value


def load_manifest(path):
    path = Path(path).resolve()
    m = json.loads(path.read_text())
    for name, asset in m.get('assets', {}).items():
        p = (path.parent / asset['path']).resolve()
        if not p.is_relative_to(path.parent) or not p.is_file():
            raise ValueError('Invalid asset path: ' + name)
        if digest(p) != asset['sha256']:
            raise ValueError('Asset hash mismatch: ' + name)
    m['_directory'] = str(path.parent)
    return m


def asset_path(manifest, key):
    p = (Path(manifest['_directory']) / manifest['assets'][key]['path']).resolve()
    if not p.is_relative_to(Path(manifest['_directory']).resolve()):
        raise ValueError('Asset outside product directory')
    return p


def read_raster(manifest, key):
    with rasterio.open(asset_path(manifest, key)) as ds:
        a = ds.read(1, masked=True).astype('float64').filled(np.nan)
        grid = {'crs': ds.crs.to_string(), 'transform': list(ds.transform)[:6], 'width': ds.width, 'height': ds.height}
    return a, grid


def write_raster(path, array, grid):
    a = np.asarray(array, dtype='float32')
    if a.ndim != 2 or a.shape != (grid['height'], grid['width']):
        raise ValueError('Raster does not match grid')
    with rasterio.open(path, 'w', driver='GTiff', width=a.shape[1], height=a.shape[0], count=1, dtype='float32', crs=grid['crs'], transform=Affine(*grid['transform']), nodata=np.nan, compress='lzw') as ds:
        ds.write(a, 1)


def same_grid(a, b):
    if a['crs'] != b['crs'] or a['width'] != b['width'] or a['height'] != b['height'] or not np.allclose(a['transform'], b['transform'], rtol=0, atol=1e-8):
        raise ValueError('Product grids differ; align inputs explicitly')


def publish(event, product, metadata, writer, output_root=None, review=False):
    """writer(stage) returns {assetKey: relativeFilename}; review gates current pointer."""
    root = Path(output_root or OUTPUT_ROOT)
    base = root / safe_name(event) / 'p3' / safe_name(product)
    base.mkdir(parents=True, exist_ok=True)
    run = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix='.stage-', dir=base) as tmp:
        stage = Path(tmp)
        files = writer(stage)
        if not isinstance(files, dict) or not files:
            raise ValueError('Publication requires at least one named asset')
        assets = {}
        for key, filename in files.items():
            p = (stage / filename).resolve()
            if not p.is_relative_to(stage.resolve()) or not p.is_file():
                raise ValueError('Invalid staged asset')
            assets[key] = {'path': filename, 'sha256': digest(p)}
        m = {k:v for k,v in metadata.items() if k != '_directory'}
        m.setdefault('sourceRunIds', m.get('upstreamRunIds', []))
        if m.get('dataKind') not in ('observed','derived','scenario','synthetic'):
            raise ValueError('Explicit dataKind is required')
        if m.get('syntheticLineage'):
            m['dataKind'] = 'synthetic'
        m.update(schemaVersion='1.0', event=event, product=product, runId=run, assets=assets, createdAt=datetime.now(timezone.utc).isoformat(), implementationStatus=m.get('implementationStatus', 'pending'), dataStatus='needs-review')
        # Publication is not scientific review; only synthetic fixtures may auto-select.
        m['dataStatus'] = 'synthetic' if m['dataKind']=='synthetic' else 'needs-review'
        (stage/'manifest.json').write_text(json.dumps(m, indent=2, allow_nan=False)+'\n')
        os.rename(stage, base/run)
    if m['dataKind']=='synthetic' and review:
        pointer = base / ('.current-'+run+'.json')
        pointer.write_text(json.dumps({'runId':run}))
        os.replace(pointer, base/'current.json')
    return base/run/'manifest.json'
