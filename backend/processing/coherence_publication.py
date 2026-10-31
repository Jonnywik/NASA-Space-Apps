"""Import reviewed-format legacy change outputs into the immutable catalog.

Import preserves data kind and does not perform scientific review. Existing
P3 catalog storage is reused; its historical directory name is retained.
"""
import json
from pathlib import Path
import shutil
import numpy as np
import rasterio
from .p3 import core


def import_change(event, metadata_path, output_root=None):
    path = Path(metadata_path).resolve()
    data = json.loads(path.read_text())
    if data.get('event') != event or data.get('schemaVersion') != '1.0':
        raise ValueError('Change metadata identity/schema mismatch')
    core.safe_name(event)
    if data.get('dataKind') not in ('observed', 'derived', 'synthetic'):
        raise ValueError('Change metadata must declare observed/derived/synthetic dataKind')
    for field in ('runId', 'prePair', 'coPair', 'parameters', 'sources', 'grid', 'stats', 'coverage'):
        if not data.get(field):
            raise ValueError('Missing change metadata: ' + field)
    files = {'changeMask': 'change_mask.tif', 'changeGeometry': 'change.geojson', 'qa': '06_change_check.png'}
    for filename in files.values():
        info = data.get('outputs', {}).get(filename, {})
        asset = (path.parent / filename).resolve()
        if not asset.is_relative_to(path.parent) or not asset.is_file() or core.digest(asset) != info.get('sha256'):
            raise ValueError('Legacy output missing or hash mismatch: ' + filename)
    with rasterio.open(path.parent / files['changeMask']) as ds:
        if ds.count != 1 or ds.crs is None:
            raise ValueError('Change mask requires single band and CRS')
        values = ds.read(1, masked=True).astype(float).filled(np.nan)
        if not np.isfinite(values).any():
            raise ValueError('Change mask has no valid support')
        if not np.isin(values[np.isfinite(values)], [0, 1]).all():
            raise ValueError('Change mask must be 0/1 with explicit nodata')
        grid = {'crs': ds.crs.to_string(), 'transform': list(ds.transform)[:6], 'width': ds.width, 'height': ds.height}
        core.same_grid(grid, data['grid'])
        if ds.tags().get('event') != event or ds.tags().get('extractionId') != data.get('extractionId'):
            raise ValueError('Change mask lineage differs from metadata')
        if ds.tags().get('dataKind') != data['dataKind']:
            raise ValueError('Change mask data kind differs from metadata')
        if int(np.count_nonzero(values == 1)) != data['stats'].get('changedPixelCount'):
            raise ValueError('Change mask counts differ from metadata')
        if int(np.isfinite(values).sum()) != data['coverage'].get('supportedPixelCount'):
            raise ValueError('Change mask support differs from metadata')
    geometry = json.loads((path.parent / files['changeGeometry']).read_text())
    if geometry.get('type') != 'FeatureCollection':
        raise ValueError('Change geometry must be a GeoJSON FeatureCollection')
    metadata = {k: data[k] for k in ('dataKind','prePair','coPair','parameters','sources','stats','coverage','warnings','eventWindow') if k in data}
    metadata.update(grid=grid, comparisonId=data['extractionId'], sourceRunIds=[data['runId']],
                    sourceHashes={'legacyManifest': core.digest(path), **{name: core.digest(path.parent / filename) for name, filename in files.items()}},
                    algorithmVersion='paired-coherence-change-1.0', syntheticLineage=data['dataKind']=='synthetic',
                    interpretation='Coherence decrease; not confirmed damage or causal attribution')
    def writer(stage):
        for filename in files.values():
            shutil.copyfile(path.parent / filename, stage / filename)
        shutil.copyfile(path, stage / 'legacy_metadata.json')
        return {**files, 'legacyMetadata': 'legacy_metadata.json'}
    return core.publish(event, 'coherence-change', metadata, writer, output_root=output_root)
