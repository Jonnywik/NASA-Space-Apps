"""Promote a product using an operator-supplied scientific review receipt."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from processing.p3.catalog import promote

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('review', help='JSON receipt: exact manifest hash, reviewer, evidence, lineage and validated status')
    args = parser.parse_args()
    promote(args.manifest, args.review)
