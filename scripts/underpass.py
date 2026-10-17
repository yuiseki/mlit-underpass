"""Shared pieces: reading the map page, parsing the GeoJSON blocks, assigning prefectures."""

import re

PAGE_URL = "https://www.mlit.go.jp/road/saigai/underpass/map/map.html"
BASE = "https://www.mlit.go.jp/road/saigai/underpass/map/"
INDEX_URL = "https://www.mlit.go.jp/road/road_fr4_000208.html"
EXPECTED_BLOCKS = 10
EXPECTED_POINTS = 3841
# The block a file belongs to, by its code in the file name (the page's own labels).
BLOCKS = {
    "81hkd": "北海道地方",
    "82thk": "東北地方",
    "83knt": "関東地方",
    "84hkr": "北陸地方",
    "85cyb": "中部地方",
    "86knk": "近畿地方",
    "87cgk": "中国地方",
    "88skk": "四国地方",
    "89ksy": "九州地方",
    "90oki": "沖縄地方",
}


def geo_metadata() -> dict:
    """The GeoParquet 1.1 ``geo`` metadata of the point files.

    ``crs`` is left out on purpose: the spec reads that as OGC:CRS84 (longitude, latitude), which is
    what the map's coordinates are. A string such as "EPSG:4326" is not valid there (a PROJJSON
    object or null only), and DuckDB refuses the file.
    """
    return {
        "version": "1.1.0",
        "primary_column": "geometry",
        "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["Point"]}},
    }


def parse_blocks(html: str) -> list[str]:
    """The relative GeoJSON paths the page loads, in page order."""
    paths = re.findall(r"'geojson'\s*:\s*'\./([^']+)'", html)
    if len(paths) != EXPECTED_BLOCKS:
        raise ValueError(f"{len(paths)} geojson paths on the page, expected {EXPECTED_BLOCKS}")
    for p in paths:
        if not re.fullmatch(r"json/\d{2}[a-z]{3}\.geojson", p):
            raise ValueError(f"odd path {p!r}")
        if p[5:10] not in BLOCKS:
            raise ValueError(f"unknown block in {p!r}")
    return paths


def block_of(path: str) -> str:
    """Block label from a path or file name such as json/83knt.geojson."""
    m = re.search(r"(\d{2}[a-z]{3})\.geojson$", path)
    if not m or m.group(1) not in BLOCKS:
        raise ValueError(f"unknown block file {path!r}")
    return BLOCKS[m.group(1)]


def parse_features(doc: dict) -> list[dict]:
    """Rows from one block. Anything but a Point with the three expected properties raises."""
    rows = []
    for i, f in enumerate(doc["features"]):
        g = f["geometry"]
        if g["type"] != "Point":
            raise ValueError(f"feature {i}: {g['type']}, expected Point")
        p = f["properties"]
        missing = [k for k in ("name", "路線名", "管理者") if k not in p]
        if missing:
            raise ValueError(f"feature {i}: missing {missing}")
        lon, lat = g["coordinates"][:2]
        rows.append(
            {
                "name": p["name"],
                "route": p["路線名"],
                "manager": p["管理者"],
                "lon": float(lon),
                "lat": float(lat),
            }
        )
    return rows


def assign_prefecture(points, polygons, codes):
    """Prefecture code for each (lon, lat): the polygon containing it, else the nearest one
    (the census boundaries stop at the coast, so a point on a quay can fall just outside).

    Returns (codes, distances): distance in degrees, 0.0 when inside.
    """
    from shapely import STRtree
    from shapely.geometry import Point

    tree = STRtree(polygons)
    out, dist = [], []
    for lon, lat in points:
        pt = Point(lon, lat)
        hit = [i for i in tree.query(pt, predicate="within")]
        if hit:
            out.append(codes[hit[0]])
            dist.append(0.0)
        else:
            i = int(tree.nearest(pt))
            out.append(codes[i])
            dist.append(float(polygons[i].distance(pt)))
    return out, dist
