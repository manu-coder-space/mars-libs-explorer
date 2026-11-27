#!/usr/bin/env python3
"""Validate the pinned Mar-to-gis sources and their distinct spatial coverage."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SOURCE_DIR = DIST / "Mar-to-gis" / "data"


def read(path):
    return json.loads(path.read_text())


def coordinates(value):
    if isinstance(value, list) and len(value) >= 2 and isinstance(value[0], (int, float)):
        yield value
    else:
        for item in value:
            yield from coordinates(item)


def bounds(features):
    values = list(p for f in features for p in coordinates(f["geometry"]["coordinates"]))
    return [min(p[0] for p in values), min(p[1] for p in values), max(p[0] for p in values), max(p[1] for p in values)]


def main():
    path = SOURCE_DIR / "jezero-lines.geojson"
    lines = read(path)
    manifest = read(SOURCE_DIR / "sources.json")
    source = manifest["sources"][0]
    layer = manifest["layers"][0]
    expected = {"contact": 2496, "channel": 6, "crater_rim": 66, "buried_crater": 4, "ridge_crest": 176, "lineament": 98, "delta_front": 32}
    assert hashlib.sha256(path.read_bytes()).hexdigest() == layer["sha256"], "Line file does not match its manifest hash"
    assert lines["coordinate_system"]["not_earth_wgs84"] is True
    assert lines["coordinate_system"]["esri_wkid"] == 104971
    assert lines["coordinate_system"]["sphere_radius_m"] == 3396190
    assert len(lines["features"]) == source["display_feature_count"] == layer["feature_count"] == 2878
    assert dict(Counter(f["properties"]["kind"] for f in lines["features"])) == expected
    assert len({f["id"] for f in lines["features"]}) == 2878, "Duplicate source feature IDs"
    rendered = [f for f in lines["features"] if f["properties"]["label"] != "boundary"]
    assert len(rendered) == 2877
    assert sum(f["properties"]["kind"] == "contact" for f in rendered) == 2495
    assert sum(f["properties"]["kind"] != "contact" for f in rendered) == 382
    vertex_count = 0
    for f in lines["features"]:
        props = f["properties"]
        assert props["label"] == props["original_attributes"]["TYPE"]
        assert props["source_object_id"] == props["original_attributes"]["OBJECTID"]
        assert props["source_id"] == "jezero_sim3464"
        assert props["source_url"] == "https://doi.org/10.3133/sim3464"
        assert f["geometry"]["type"] in ("LineString", "MultiLineString")
        paths = [f["geometry"]["coordinates"]] if f["geometry"]["type"] == "LineString" else f["geometry"]["coordinates"]
        assert all(len(p) >= 2 for p in paths), "Non-drawable line part"
        for p in coordinates(f["geometry"]["coordinates"]):
            assert len(p) == 2 and all(math.isfinite(v) for v in p)
            assert 76.79 <= p[0] <= 77.81 and 17.69 <= p[1] <= 18.71, "Line coordinate outside the source map region"
            vertex_count += 1
    assert vertex_count == source["processing"]["display_coordinate_count"]
    assert bounds(lines["features"]) == layer["bounds"]
    assert [(v["source_layer_id"], v["source_object_id"]) for v in source["omitted_records"]] == [(5, 4879)]

    geography = read(DIST / "data" / "geography.json")
    polygon_meta = geography["missions"]["supercam"]["geology"]
    polygon_path = DIST / polygon_meta["geojson"]
    polygons = read(polygon_path)
    assert hashlib.sha256(polygon_path.read_bytes()).hexdigest() == polygon_meta["sha256"]
    assert len(polygons["features"]) == polygon_meta["feature_count"] == 229
    assert len({f["properties"]["code"] for f in polygons["features"]}) == 11
    assert bounds(polygons["features"]) == polygon_meta["bounds"] == [77.1, 18.3, 77.59, 18.64]
    assert polygon_meta["source_feature_count"] == 1308
    # The smaller polygon excerpt must never be described as covering the full
    # regional line layer. Check the strict spatial nesting explicitly.
    pb, lb = polygon_meta["bounds"], layer["bounds"]
    assert lb[0] < pb[0] < pb[2] < lb[2] and lb[1] < pb[1] < pb[3] < lb[3]
    assert not geography["missions"]["chemcam"]["geology"].get("geojson"), "Gale grouping requires review of a new polygon source"
    assert geography["missions"]["zhurong"]["geology"]["attribution"] == "Wu et al. (2024)"
    print(json.dumps({"status": "passed", "source_features": len(lines["features"]), "rendered_features": len(rendered), "rendered_contacts": 2495, "landform_traces": 382, "display_vertices": vertex_count, "polygon_features": 229, "polygon_units": 11, "polygon_bounds": pb, "line_bounds": lb, "line_sha256": layer["sha256"]}))


if __name__ == "__main__":
    main()
