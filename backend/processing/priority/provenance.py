"""Check that a priority mask still matches its recorded flood and motion inputs."""
import json
from pathlib import Path

from processing.p3 import core


def load_priority(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'priority_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('area') != folder.parent.name or manifest.get('dataKind') not in ('derived', 'synthetic'):
        raise ValueError('Invalid priority provenance')
    source = manifest['source']
    checks = [(folder / 'priority_mask.tif', manifest['maskSha256']),
              (folder / 'rhythm_half.tif', source['rhythmMaskSha256']),
              (folder / 'manifest.json', source['rhythmManifestSha256'])]
    run = core.safe_name(source['motionRunId'])
    motion_path = folder.parent / 'p3' / 'ground-motion' / run / 'manifest.json'
    checks.append((motion_path, source['motionManifestSha256']))
    for path, expected in checks:
        if core.digest(path) != expected:
            raise ValueError('Priority mask or source has changed; rebuild priority zones')
    motion = json.loads(motion_path.read_text(encoding='utf-8'))
    motion['_directory'] = str(motion_path.parent.resolve())
    if core.digest(core.asset_path(motion, 'displacementMm')) != source['motionDisplacementSha256']:
        raise ValueError('Priority motion displacement has changed; rebuild priority zones')
    return manifest
