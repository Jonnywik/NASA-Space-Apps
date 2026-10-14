"""
check_setup.py - run this FIRST.
It checks that Python and every package we need are installed.
Run it from the tanaw-backend folder:
    python scripts/check_setup.py
"""
import sys

print("Python version:", sys.version.split()[0])

# (name you type in "import", name you type in "pip install")
packages = [
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("rasterio", "rasterio"),
    ("skimage", "scikit-image"),
    ("geopandas", "geopandas"),
    ("shapely", "shapely"),
    ("matplotlib", "matplotlib"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
]

all_ok = True
for import_name, pip_name in packages:
    try:
        module = __import__(import_name)
        version = getattr(module, "__version__", "")
        print("  OK     ", import_name, version)
    except ImportError:
        print("  MISSING", import_name, " -> pip install", pip_name)
        all_ok = False

if all_ok:
    print("\nAll good! You are ready.")
else:
    print("\nSome packages are missing. Run: pip install -r requirements.txt")