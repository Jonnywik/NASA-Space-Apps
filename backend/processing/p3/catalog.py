"""Hash-bound review receipts and immutable product selection.

Review is an operator assertion backed by evidence; this module cannot perform
scientific review. It never turns synthetic fixtures into validated observations.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from .core import OUTPUT_ROOT, digest, load_manifest, safe_name

PRODUCTS = ('gunw', 'gcov', 'los-pair', 'ground-motion', 'biomass',
            'biomass_calibration', 'roots_faults_fusion',
            'scenario-inputs', 'projection', 'briefing')


class ProductUnavailable(ValueError):
    def __init__(self, code, message, status=404):
        super().__init__(message)
        self.code, self.status = code, status


def _base(event, product, root=None):
    safe_name(event)
    if product not in PRODUCTS:
        raise ProductUnavailable('unsupported_product', 'Unsupported product', 422)
    root = Path(root or OUTPUT_ROOT).resolve()
    base = root / event / 'p3' / product
    if not base.resolve().is_relative_to(root):
        raise ProductUnavailable('invalid_path', 'Product path escapes catalog', 422)
    return base


def promote(manifest_path, review_path):
    """Require a supplied reviewer receipt tied to this exact manifest and lineage."""
    path = Path(manifest_path).resolve()
    manifest = load_manifest(path)
    receipt = json.loads(Path(review_path).read_text())
    if not isinstance(receipt, dict):
        raise ValueError('Review receipt must be a JSON object')
    if manifest['dataKind'] == 'synthetic' or manifest.get('syntheticLineage'):
        raise ValueError('Synthetic data cannot be validated')
    for field in ('reviewer', 'reviewedAt', 'evidence'):
        if not receipt.get(field):
            raise ValueError('Review requires ' + field)
    if not isinstance(receipt['reviewer'], str) or not receipt['reviewer'].strip():
        raise ValueError('Reviewer must be a nonempty identity string')
    try:
        timestamp = datetime.fromisoformat(receipt['reviewedAt'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise ValueError('Timezone required')
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('reviewedAt must be an ISO timestamp with timezone') from exc
    if receipt.get('status') != 'validated' or receipt.get('manifestSha256') != digest(path):
        raise ValueError('Review does not validate this exact manifest')
    if receipt.get('sourceRunIds') != manifest.get('sourceRunIds', []):
        raise ValueError('Review lineage does not match manifest')
    if not isinstance(receipt['evidence'], list) or not all(isinstance(x, str) and x.strip() for x in receipt['evidence']):
        raise ValueError('Evidence must be a nonempty list of review references')
    if path.parent.name != manifest['runId'] or path.parent.parent.name != manifest['product']:
        raise ValueError('Manifest is not in its registered run directory')
    # Receipt is part of the pointer: it cannot mutate the immutable run.
    pointer = {'runId': manifest['runId'], 'manifestSha256': digest(path), 'review': receipt}
    base = path.parent.parent
    temp = base / ('.current-' + manifest['runId'] + '.json')
    temp.write_text(json.dumps(pointer, indent=2) + '\n')
    os.replace(temp, base / 'current.json')


def select(event, product, run_id=None, root=None):
    base = _base(event, product, root)
    pointer = None
    if (base / 'current.json').is_file():
        pointer = json.loads((base / 'current.json').read_text())
    if run_id is None:
        if pointer is None:
            code = 'review_required' if base.is_dir() and any(base.glob('*/manifest.json')) else 'data_unavailable'
            raise ProductUnavailable(code, 'No reviewed current product', 409 if code == 'review_required' else 404)
        run_id = pointer['runId']
    safe_name(run_id)
    path = (base / run_id / 'manifest.json').resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ProductUnavailable('data_unavailable', 'Requested run does not exist')
    try:
        manifest = load_manifest(path)
    except (ValueError, KeyError, OSError) as exc:
        raise ProductUnavailable('invalid_product', 'Published product failed integrity checks', 409) from exc
    if manifest.get('event') != event or manifest.get('product') != product or manifest.get('runId') != run_id:
        raise ProductUnavailable('mismatched_run', 'Manifest identity does not match catalog', 409)
    if manifest['dataKind'] == 'synthetic':
        manifest['dataStatus'] = 'synthetic'
        return manifest
    reviewed = pointer and pointer['runId'] == run_id and pointer.get('manifestSha256') == digest(path) and pointer.get('review', {}).get('status') == 'validated'
    if not reviewed:
        raise ProductUnavailable('review_required', 'Run requires scientific review before serving', 409)
    manifest['dataStatus'] = 'validated'
    manifest['review'] = pointer['review']
    return manifest


def capabilities(event, root=None):
    result = {}
    for product in ('ground-motion', 'biomass', 'scenario-inputs', 'projection'):
        try:
            manifest = select(event, product, root=root)
            result[product] = {'available': True, 'dataStatus': manifest['dataStatus'], 'dataKind': manifest['dataKind'], 'runId': manifest['runId']}
        except ProductUnavailable as exc:
            result[product] = {'available': False, 'reason': exc.code}
        except (ValueError, KeyError, OSError):
            result[product] = {'available': False, 'reason': 'invalid_product'}
    return result
