import pytest
import underpass as u
from shapely.geometry import box

PAGE = "\n".join(f"  'x': {{ 'geojson': './json/{c}.geojson', 'zindex': 1 }}," for c in u.BLOCKS)


def test_parse_blocks_reads_ten_paths_in_page_order():
    paths = u.parse_blocks(PAGE)
    assert paths[0] == "json/81hkd.geojson" and paths[-1] == "json/90oki.geojson"
    assert len(paths) == 10


def test_parse_blocks_rejects_a_changed_page():
    with pytest.raises(ValueError):
        u.parse_blocks(PAGE.replace("90oki", "99zzz"))
    with pytest.raises(ValueError):
        u.parse_blocks(PAGE.splitlines()[0])


def test_block_of():
    assert u.block_of("json/83knt.geojson") == "関東地方"
    with pytest.raises(ValueError):
        u.block_of("json/99zzz.geojson")


def feature(typ="Point", **props):
    p = {"name": "N", "路線名": "R", "管理者": "M", "_markerType": "Icon"} | props
    return {
        "type": "Feature",
        "properties": p,
        "geometry": {"type": typ, "coordinates": [140.1, 36.2]},
    }


def test_parse_features_keeps_the_three_properties_and_drops_the_icon_settings():
    rows = u.parse_features({"features": [feature()]})
    assert rows == [{"name": "N", "route": "R", "manager": "M", "lon": 140.1, "lat": 36.2}]


def test_parse_features_fails_loudly():
    with pytest.raises(ValueError):
        u.parse_features({"features": [feature(typ="LineString")]})
    bad = feature()
    del bad["properties"]["管理者"]
    with pytest.raises(ValueError):
        u.parse_features({"features": [bad]})


def test_assign_prefecture_inside_and_nearest():
    polys = [box(0, 0, 1, 1), box(2, 0, 3, 1)]
    codes, dist = u.assign_prefecture([(0.5, 0.5), (1.9, 0.5), (2.5, 0.5)], polys, ["01", "02"])
    assert codes == ["01", "02", "02"]
    assert dist[0] == 0.0 and dist[2] == 0.0 and dist[1] == pytest.approx(0.1)


def test_geo_metadata_crs_follows_the_geoparquet_spec():
    geo = u.geo_metadata()
    col = geo["columns"]["geometry"]
    assert geo["version"] == "1.1.0" and geo["primary_column"] == "geometry"
    assert col["encoding"] == "WKB" and col["geometry_types"] == ["Point"]
    # the spec: crs is a PROJJSON object or null; leaving it out means OGC:CRS84. Never a string.
    assert "crs" not in col or col["crs"] is None or isinstance(col["crs"], dict)


def test_written_parquet_carries_that_metadata(tmp_path):
    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    t = pa.table({"geometry": [b"\x01"]}).replace_schema_metadata(
        {b"geo": json.dumps(u.geo_metadata()).encode()}
    )
    pq.write_table(t, tmp_path / "x.parquet")
    geo = json.loads(pq.read_schema(tmp_path / "x.parquet").metadata[b"geo"])
    assert not isinstance(geo["columns"]["geometry"].get("crs"), str)
