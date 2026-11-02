#!/usr/bin/env python3
"""Tanaw helper for HyP3 / Sentinel-1 InSAR work.

Put this file in backend/scripts/ and run it from backend/ with the venv active.

  python scripts/hyp3_tools.py credits
  python scripts/hyp3_tools.py history
  python scripts/hyp3_tools.py find --event karding_2022 --start 2022-08-20 --end 2022-10-10
  python scripts/hyp3_tools.py submit data/raw/karding_2022/insar/jobs.json          (dry run)
  python scripts/hyp3_tools.py submit data/raw/karding_2022/insar/jobs.json --go     (really submits)
  python scripts/hyp3_tools.py status --prefix kard22
  python scripts/hyp3_tools.py download --prefix kard22 --dest data/raw/karding_2022/insar

jobs.json looks like:
  {"jobs": [{"name": "kard22_pre1", "reference": "S1A_IW_SLC__1SDV_2022...",
             "secondary": "S1A_IW_SLC__1SDV_2022..."}]}
"reference" is the EARLIER scene, "secondary" the LATER one. Job names: max 20 characters,
letters, digits, "-" and "_" only.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
SCENE_RE = re.compile(r"^S1[ABCD]_IW_SLC__1S[SD][VH]_(\d{8})T\d{6}_")
CREDITS = {"10x2": 15, "20x4": 10}  # HyP3 credit cost per InSAR job (HyP3 docs)


def login():
    from hyp3_sdk import HyP3
    try:
        api = HyP3()
        api.check_credits()
        return api
    except Exception:
        print("No saved login worked. Enter your NASA Earthdata username and password.")
        print("(Typing a password shows nothing on screen - that is normal.)")
        return HyP3(prompt="password")


def scene_date(name):
    m = SCENE_RE.match(name or "")
    if not m:
        return None
    d = m.group(1)
    return date(int(d[:4]), int(d[4:6]), int(d[6:8]))


# ---------------------------------------------------------------- credits
def cmd_credits(a):
    print("Remaining HyP3 credits:", login().check_credits())


# ---------------------------------------------------------------- history
def cmd_history(a):
    api = login()
    jobs = [j for j in api.find_jobs(job_type="RTC_GAMMA")]
    if not jobs:
        print("No RTC jobs found on this account. Use Vertex or ask whoever ran the flood data.")
        return
    granules = []
    for j in jobs:
        gs = (j.job_parameters or {}).get("granules", [])
        print(f"{j.name or '-':20s} {j.status_code:10s} {', '.join(gs)}")
        granules += gs
    try:
        import asf_search as asf
        res = asf.granule_search(sorted(set(granules)))
        print("\nTrack info for those scenes (relative orbit / direction / frame):")
        for p in sorted(res, key=lambda r: r.properties.get("startTime", "")):
            q = p.properties
            print(q.get("startTime", "")[:10], "orbit", q.get("pathNumber"), q.get("flightDirection"),
                  "frame", q.get("frameNumber"), q.get("sceneName"))
    except Exception as e:  # lookup is a convenience only
        print("\n(Could not look up track info automatically:", e, ")")


# ---------------------------------------------------------------- find
def aoi_point(a):
    if a.event:
        p = Path("data/output") / a.event / "overlays.json"
        try:
            b = json.loads(p.read_text(encoding="utf-8"))["bounds"]
            (s, w), (n, e) = b
            return f"POINT({(w + e) / 2:.5f} {(s + n) / 2:.5f})"
        except Exception as ex:
            sys.exit(f"Could not read bounds from {p} ({ex}). Use --lon and --lat instead.")
    if a.lon is None or a.lat is None:
        sys.exit("Give --event NAME, or both --lon and --lat.")
    return f"POINT({a.lon} {a.lat})"


def cmd_find(a):
    import asf_search as asf
    opts = dict(
        intersectsWith=aoi_point(a), platform=[asf.PLATFORM.SENTINEL1],
        processingLevel=asf.PRODUCT_TYPE.SLC, beamMode=asf.BEAMMODE.IW,
        start=a.start, end=a.end, maxResults=500)
    if a.orbit:
        opts["relativeOrbit"] = a.orbit
    if a.direction:
        opts["flightDirection"] = a.direction.upper()
    res = asf.geo_search(**opts)
    if not res:
        print("No Sentinel-1 IW SLC scenes found for that place and date range.")
        return
    groups = defaultdict(list)
    for p in res:
        q = p.properties
        groups[(q.get("pathNumber"), q.get("flightDirection"), q.get("frameNumber"))].append(q)
    for (orbit, direction, frame), items in sorted(groups.items(), key=lambda kv: str(kv[0])):
        items.sort(key=lambda q: q["startTime"])
        print(f"\n=== relative orbit {orbit} | {direction} | frame {frame} | {len(items)} scenes ===")
        prev = None
        for q in items:
            d = date.fromisoformat(q["startTime"][:10])
            gap = f"+{(d - prev).days:3d} d" if prev else "       "
            prev = d
            print(f"{d}  {gap}  {q.get('platform', ''):14s} {q.get('polarization', ''):6s} {q['sceneName']}")
    print("\nPick ONE orbit/direction/frame group, then take all scenes from that same group.")


# ---------------------------------------------------------------- submit
def load_jobs(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    jobs = data["jobs"] if isinstance(data, dict) else data
    problems, seen = [], set()
    for i, j in enumerate(jobs, 1):
        tag = f"job {i} ({j.get('name', '?')})"
        n, r, s = j.get("name", ""), j.get("reference", ""), j.get("secondary", "")
        if not NAME_RE.match(n):
            problems.append(f"{tag}: name must be 1-20 characters of letters, digits, - or _")
        if n in seen:
            problems.append(f"{tag}: duplicate name")
        seen.add(n)
        dr, ds = scene_date(r), scene_date(s)
        if not dr or not ds:
            problems.append(f"{tag}: reference/secondary must be Sentinel-1 IW SLC scene names "
                            "(S1A_IW_SLC__1SDV_...). Did you copy a GRD or RTC name by mistake?")
        elif dr >= ds:
            problems.append(f"{tag}: reference must be the EARLIER scene")
        if r == s:
            problems.append(f"{tag}: the two scenes are the same")
    return jobs, problems


def cmd_submit(a):
    jobs, problems = load_jobs(a.jobs_file)
    print(f"{len(jobs)} jobs, looks {a.looks}, about {len(jobs) * CREDITS[a.looks]} credits")
    for j in jobs:
        dr, ds = scene_date(j["reference"]), scene_date(j["secondary"])
        gap = (ds - dr).days if dr and ds else "?"
        warn = "  <- long gap, coherence will be low" if isinstance(gap, int) and gap > 48 else ""
        print(f"  {j['name']:20s} {dr} -> {ds}  ({gap} days){warn}")
    if problems:
        print("\nFIX THESE FIRST:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    if not a.go:
        print("\nDRY RUN ONLY - nothing was sent. Add --go to submit for real.")
        return
    api = login()
    print("Credits before:", api.check_credits())
    for j in jobs:
        old = [x for x in api.find_jobs(name=j["name"]) if x.status_code != "FAILED"]
        if old:
            print(f"  skip {j['name']}: already exists ({old[0].status_code})")
            continue
        b = api.submit_insar_job(j["reference"], j["secondary"], name=j["name"], looks=a.looks)
        print(f"  submitted {j['name']}  id={b.jobs[0].job_id}")
    print("Credits after:", api.check_credits())


# ---------------------------------------------------------------- status / download
def my_jobs(api, prefix, days=60):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return [j for j in api.find_jobs(start=start, job_type="INSAR_GAMMA")
            if (j.name or "").startswith(prefix)]


def cmd_status(a):
    jobs = my_jobs(login(), a.prefix)
    if not jobs:
        print("No jobs found with that prefix.")
        return
    for j in sorted(jobs, key=lambda x: x.name or ""):
        print(f"{j.name:20s} {j.status_code:10s} expires: {getattr(j, 'expiration_time', None)}")
        if j.status_code == "FAILED":
            print("     logs:", getattr(j, "logs", None))
    counts = defaultdict(int)
    for j in jobs:
        counts[j.status_code] += 1
    print("\nSummary:", dict(counts))
    if a.save:
        Path(a.save).parent.mkdir(parents=True, exist_ok=True)
        Path(a.save).write_text(json.dumps([j.to_dict() for j in jobs], indent=2, default=str),
                                encoding="utf-8")
        print("Saved job records to", a.save)


def cmd_download(a):
    jobs = [j for j in my_jobs(login(), a.prefix) if j.succeeded()]
    if not jobs:
        print("No SUCCEEDED jobs with that prefix yet.")
        return
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        names = [f["filename"] for f in (j.files or [])]
        if names and all((dest / n).exists() for n in names):
            print(f"  have {j.name}: {names[0]}")
            continue
        got = j.download_files(dest)
        print(f"  downloaded {j.name}: {got[0].name if got else '?'}")
    print("Zip files are in", dest.resolve(), "- do NOT unzip them.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("credits").set_defaults(fn=cmd_credits)
    sub.add_parser("history").set_defaults(fn=cmd_history)
    f = sub.add_parser("find")
    f.add_argument("--event")
    f.add_argument("--lon", type=float)
    f.add_argument("--lat", type=float)
    f.add_argument("--start", required=True)
    f.add_argument("--end", required=True)
    f.add_argument("--orbit", type=int)
    f.add_argument("--direction", choices=["ascending", "descending", "ASCENDING", "DESCENDING"])
    f.set_defaults(fn=cmd_find)
    s = sub.add_parser("submit")
    s.add_argument("jobs_file")
    s.add_argument("--looks", choices=["10x2", "20x4"], default="10x2")
    s.add_argument("--go", action="store_true")
    s.set_defaults(fn=cmd_submit)
    st = sub.add_parser("status")
    st.add_argument("--prefix", required=True)
    st.add_argument("--save")
    st.set_defaults(fn=cmd_status)
    d = sub.add_parser("download")
    d.add_argument("--prefix", required=True)
    d.add_argument("--dest", required=True)
    d.set_defaults(fn=cmd_download)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
