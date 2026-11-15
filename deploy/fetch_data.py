"""Download the Tanaw data package parts, verify the SHA-256, and unzip at the repository root (used by the hosted build).

    python deploy/fetch_data.py [--base URL] [--sha256 HEX] [--dest DIR]
"""
import argparse
import hashlib
import io
import sys
import urllib.request
import zipfile

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="https://raw.githubusercontent.com/Jonnywik/tanaw-nasa-space-apps-2026/data-package-v1")
ap.add_argument("--sha256", default="3290a66b2fc115bd666c1f199c17c7e5d0c6f978132264eb28335219110a2cfa")
ap.add_argument("--dest", default=".")
a = ap.parse_args()

buf = io.BytesIO()
for i in ("00", "01", "02", "03"):
    url = f"{a.base}/tanaw-data-camanava_2026-v1.zip.part{i}"
    with urllib.request.urlopen(url, timeout=300) as r:
        buf.write(r.read())
    print(f"downloaded part{i}: {buf.tell():,} bytes so far", flush=True)
digest = hashlib.sha256(buf.getvalue()).hexdigest()
if digest != a.sha256:
    sys.exit(f"checksum mismatch: {digest} != {a.sha256}")
zipfile.ZipFile(buf).extractall(a.dest)
print("data package verified and unzipped", flush=True)
