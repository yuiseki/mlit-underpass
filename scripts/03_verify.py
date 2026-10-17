"""Check the Parquet against the downloaded files and the manifest.

uv run python scripts/03_verify.py [--version 2026-10-17]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq
import underpass as u

ROOT = Path(__file__).parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2026-10-17")
    a = ap.parse_args()
    raw = ROOT / "data" / "raw" / a.version
    manifest = json.loads((raw / "MANIFEST.json").read_text())
    problems = []
    src = []
    for name, meta in manifest["files"].items():
        body = (raw / name).read_bytes()
        if hashlib.sha256(body).hexdigest() != meta["sha256"] or len(body) != meta["bytes"]:
            problems.append(f"{name}: differs from the manifest")
        src += u.parse_features(json.loads(body))
    if len(src) != u.EXPECTED_POINTS:
        problems.append(f"{len(src)} source points, expected {u.EXPECTED_POINTS}")
    nat = pq.read_table(ROOT / "data/parquet/national.parquet").to_pylist()
    if len(nat) != len(src):
        problems.append(f"national has {len(nat)} rows, source {len(src)}")
    for i, (r, s) in enumerate(zip(nat, src, strict=False)):
        if (r["name"], r["route"], r["manager"], r["lon"], r["lat"]) != (
            s["name"],
            s["route"],
            s["manager"],
            s["lon"],
            s["lat"],
        ):
            problems.append(f"row {i}: differs from the source")
            break
    if len({r["id"] for r in nat}) != len(nat):
        problems.append("ids are not unique")
    per = []
    for f in sorted((ROOT / "data/parquet/prefectures").glob("*.parquet")):
        rows = pq.read_table(f).to_pylist()
        if {r["pref_code"] for r in rows} != {f.stem}:
            problems.append(f"{f.name}: wrong prefecture code inside")
        per += rows
    if sorted(r["id"] for r in per) != sorted(r["id"] for r in nat):
        problems.append("the prefecture files do not add up to the national file")
    if any(r["pref_dist_deg"] > 0 for r in nat):
        problems.append("points outside every prefecture polygon")
    print(f"{len(nat)} national rows, {len(per)} rows in prefecture files")
    for p in problems:
        print("PROBLEM:", p)
    print("OK" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
