"""Import hash-bound change outputs; scientific review uses script 17 separately."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from processing.coherence_publication import import_change

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('event')
    parser.add_argument('--metadata', required=True, help='legacy change_extent.json from script 06')
    parser.add_argument('--output-root')
    args = parser.parse_args()
    try:
        print(import_change(args.event, args.metadata, args.output_root))
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc)+'\n')
if __name__ == '__main__':
    main()
