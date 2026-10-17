"""Write data/README.md (the dataset card), data/LICENSE and data/provenance.yaml.

uv run python scripts/04_card.py [--version 2026-10-17]
"""

import argparse
import json
import sys
from pathlib import Path

import underpass as u

ROOT = Path(__file__).parents[1]
REPO = "mlit-underpass-2026-10"

CARD = """---
license: cc-by-4.0
pretty_name: MLIT underpass map (全国のアンダーパス箇所マップ)
language:
- ja
tags:
- geospatial
- japan
- road
- flood
- underpass
size_categories:
- 1K<n<10K
---

# {repo}

The points of the national underpass map (全国のアンダーパス箇所マップ) of the Ministry of Land,
Infrastructure, Transport and Tourism (国土交通省 道路局): {rows:,} points of road sections that
are much lower than the sections before and after them, where heavy rain can flood the road.
One file for all of Japan and one file per prefecture, as GeoParquet.

## Source

- Map page: <{page}>, which loads {nfiles} GeoJSON blocks (one per regional bureau).
- Index page: <{index}>, which gives the count ("about 3,800 places") and the date of the map (R7.3.31).
- Fetched {fetched}. The server states Last-Modified {lm} for the page and the blocks.
  The blocks are kept unchanged under `raw/{version}/` with their sha256 in `MANIFEST.json`.

## Files

| Path | Content |
|---|---|
| `parquet/national.parquet` | all {rows:,} points |
| `parquet/prefectures/<code>.parquet` | the points of one prefecture, 2-digit JIS code ({nfiles_pref} files; every prefecture has at least one point) |
| `parquet/columns.json` | the counts |
| `raw/{version}/*.geojson` | the {nfiles} blocks as published |

## Columns

| Column | Content |
|---|---|
| `id` | block code and the order in that block's file, such as `83knt-0001` |
| `block` | the regional block of the page (関東地方 etc.) |
| `name` | the point's name as published |
| `route` | the route name as published (`路線名`) |
| `manager` | the road manager as published (`管理者`): a bureau, a prefecture or a municipality |
| `pref_code`, `pref` | the prefecture, found here from the point (see below), not published by the source |
| `pref_dist_deg` | 0 when the point lies inside the prefecture polygon, otherwise the distance to the nearest one in degrees; {outside} points are outside |
| `lon`, `lat` | the coordinates as published |
| `geometry` | the same point as WKB; EPSG:4326 as the map draws it (the source states no CRS) |

## What was changed

- The three properties of each feature were renamed (`name`, `路線名` to `route`, `管理者` to
  `manager`); the map's icon settings were dropped.
- `pref_code` and `pref` were added by testing each point against the 47 prefecture polygons of
  [yuiseki/jp-admin-2026-09](https://huggingface.co/datasets/yuiseki/jp-admin-2026-09) (CC BY 4.0).
- Nothing was removed, corrected or deduplicated.

## Known issues

- The source has no attribute besides name, route and manager. There is no depth, no
  closure rule and no date per point.
- The map is as of R7.3.31 (31 March 2025), although the page was updated later.
- {dups} rows repeat the name, route and manager of another row; {dups_same} of those groups also
  repeat the coordinates. Most are different places with the same name. All are kept so that the
  count stays {rows:,}.
- One point lies in Ehime but names Kochi Prefecture as its manager (`88skk-0101`); this is as published.
- The managers are mostly prefectures and municipalities. The page states no third-party rights
  for these points, but the MLIT terms exclude content for which another rule is stated.

## Licence

The page falls under the MLIT site terms, <https://www.mlit.go.jp/link.html>: Public Data License
1.0 (PDL1.0) unless another rule is stated, which is compatible with CC BY 4.0. This dataset is
offered under CC BY 4.0. Credit, as the terms ask:

> 出典：「全国のアンダーパス箇所マップ」（国土交通省）（{page}）をもとに作成

Say that it was processed (加工して作成) if you change it, and do not present the changed data as
if the national government had made it.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2026-10-17")
    a = ap.parse_args()
    manifest = json.loads((ROOT / "data/raw" / a.version / "MANIFEST.json").read_text())
    cols = json.loads((ROOT / "data/parquet/columns.json").read_text())
    import pyarrow.parquet as pq

    t = pq.read_table(
        ROOT / "data/parquet/national.parquet", columns=["name", "route", "manager", "lon", "lat"]
    )
    rows = t.to_pylist()
    groups: dict[tuple, list] = {}
    for r in rows:
        groups.setdefault((r["name"], r["route"], r["manager"]), []).append((r["lon"], r["lat"]))
    dups = sum(len(v) - 1 for v in groups.values() if len(v) > 1)
    dups_same = sum(1 for v in groups.values() if len(v) > 1 and len(set(v)) == 1)
    lms = {m["last_modified"] for m in manifest["files"].values()} | {
        manifest["page_last_modified"]
    }
    card = CARD.format(
        repo=REPO,
        rows=cols["rows"],
        page=u.PAGE_URL,
        index=u.INDEX_URL,
        nfiles=len(manifest["files"]),
        nfiles_pref=cols["prefecture_files"],
        version=a.version,
        fetched=manifest["fetched_at"][:10],
        lm=" / ".join(sorted(lms)),
        outside=cols["points_outside_every_polygon"],
        dups=dups,
        dups_same=dups_same,
    )
    data = ROOT / "data"
    (data / "README.md").write_text(card, encoding="utf-8")
    (data / "LICENSE").write_text(
        "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/legalcode)\n\n"
        "The underpass points are from 「全国のアンダーパス箇所マップ」 of the Ministry of Land,\n"
        "Infrastructure, Transport and Tourism, published under the Public Data License 1.0\n"
        "(see https://www.mlit.go.jp/link.html), processed as described in README.md.\n"
        "Credit: 出典：「全国のアンダーパス箇所マップ」（国土交通省）（"
        + u.PAGE_URL
        + "）をもとに作成\n"
        "The prefecture columns use yuiseki/jp-admin-2026-09 (CC BY 4.0).\n",
        encoding="utf-8",
    )
    (data / "provenance.yaml").write_text(
        f"source: {u.PAGE_URL}\nindex: {u.INDEX_URL}\nterms: https://www.mlit.go.jp/link.html\n"
        f"fetched_at: {manifest['fetched_at']}\nlast_modified: {sorted(lms)}\n"
        "prefecture_polygons: yuiseki/jp-admin-2026-09 (prefectures.parquet)\n",
        encoding="utf-8",
    )
    print("wrote data/README.md, LICENSE, provenance.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
