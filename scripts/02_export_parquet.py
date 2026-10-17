"""Write the national GeoParquet and one GeoParquet per prefecture from the downloaded blocks.

Each row: id (block code and the point's order in its file), block, name, route, manager,
pref_code, pref (from the 47 prefecture polygons of yuiseki/jp-admin-2026-09, CC BY 4.0),
pref_dist_deg (0 when the point lies inside the polygon, else the distance to the nearest one),
lon, lat and geometry (WKB point, EPSG:4326 as the page's map draws it; the file states no CRS).
data/parquet/national.parquet holds all points; data/parquet/prefectures/<code>.parquet the points of
one prefecture (prefectures without points get no file).

    uv run python scripts/02_export_parquet.py [--version 2026-10-17] [--admin PATH]
"""

import argparse
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import underpass as u
from shapely import from_wkb
from shapely.geometry import Point

ROOT = Path(__file__).parents[1]
ADMIN = Path("/sata_hdd_24tb/hf_data/__published/jp-admin-2026-09/data/prefectures.parquet")
GEO = {
    "version": "1.1.0",
    "primary_column": "geometry",
    "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["Point"], "crs": "EPSG:4326"}},
}


def write(rows: list[dict], path: Path) -> None:
    t = pa.Table.from_pylist(rows).replace_schema_metadata({b"geo": json.dumps(GEO).encode()})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, path, compression="zstd")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2026-10-17")
    ap.add_argument("--admin", type=Path, default=ADMIN)
    a = ap.parse_args()
    raw = ROOT / "data" / "raw" / a.version
    manifest = json.loads((raw / "MANIFEST.json").read_text())
    rows = []
    for name, meta in manifest["files"].items():
        feats = u.parse_features(json.loads((raw / name).read_text(encoding="utf-8")))
        code = name.split(".")[0]
        for i, r in enumerate(feats):
            rows.append({"id": f"{code}-{i + 1:04d}", "block": meta["block"], **r})
    if len(rows) != u.EXPECTED_POINTS:
        raise SystemExit(f"{len(rows)} points, expected {u.EXPECTED_POINTS}")
    adm = pq.read_table(a.admin, columns=["pref_code", "pref", "geometry"]).to_pydict()
    polys = list(from_wkb(adm["geometry"]))
    codes, dist = u.assign_prefecture([(r["lon"], r["lat"]) for r in rows], polys, adm["pref_code"])
    names = dict(zip(adm["pref_code"], adm["pref"], strict=True))
    for r, c, d in zip(rows, codes, dist, strict=True):
        r["pref_code"], r["pref"], r["pref_dist_deg"] = c, names[c], d
        r["geometry"] = Point(r["lon"], r["lat"]).wkb
    cols = [
        "id",
        "block",
        "name",
        "route",
        "manager",
        "pref_code",
        "pref",
        "pref_dist_deg",
        "lon",
        "lat",
        "geometry",
    ]
    rows = [{k: r[k] for k in cols} for r in rows]
    out = ROOT / "data" / "parquet"
    write(rows, out / "national.parquet")
    counts = {}
    for c in sorted(set(codes)):
        sub = [r for r in rows if r["pref_code"] == c]
        write(sub, out / "prefectures" / f"{c}.parquet")
        counts[c] = len(sub)
    outside = sum(1 for d in dist if d > 0)
    (out / "columns.json").write_text(
        json.dumps(
            {
                "rows": len(rows),
                "prefecture_files": len(counts),
                "counts": counts,
                "points_outside_every_polygon": outside,
                "max_dist_deg": max(dist),
            },
            indent=1,
        )
        + "\n"
    )
    print(
        f"{len(rows)} points, {len(counts)} prefecture files, {outside} points outside every "
        f"polygon (max {max(dist):.5f} deg)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
