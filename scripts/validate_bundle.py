#!/usr/bin/env python3
"""Check science-data integrity and the portable website's required assets."""
from __future__ import annotations
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
COMMON = {"SiO2", "TiO2", "Al2O3", "FeOT", "MgO", "CaO", "Na2O", "K2O"}


def validate(name):
    meta = json.loads((DIST / "data" / f"{name}.json").read_text())
    assert meta["point_files"] == [item["file"] for item in meta["packaging"]["chunks"]]
    if meta.get("point_files_gzip"):
        assert meta["point_files_gzip"] == [file + ".gz" for file in meta["point_files"]]
    assert len(meta["point_files"]) == len(set(meta["point_files"]))
    points = []
    for item in meta["packaging"]["chunks"]:
        path = DIST / item["file"]
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item["sha256"], path
        assert len(raw) == item["bytes"], path
        gzip_path = Path(str(path) + ".gz")
        if meta.get("point_files_gzip"):
            assert gzip.decompress(gzip_path.read_bytes()) == raw, path
        chunk = json.loads(raw)
        assert len(chunk) == item["point_count"]
        assert len(raw) <= 6_000_000
        points.extend(chunk)
    assert len(points) == meta["packaging"]["point_count"]
    indexed = {p["id"]: p for p in points}
    assert len(indexed) == len(points), "duplicate point identifiers"
    source_ids = {s["id"] for s in meta["sources"]}
    assert len(source_ids) == len(meta["sources"]), "duplicate source identifiers"
    for source in meta["sources"]:
        assert source["url"].startswith("https://"), source["id"]
        assert re.fullmatch(r"[0-9a-f]{64}", source["sha256"]), source["id"]
        assert isinstance(source["bytes"], int) and source["bytes"] > 0, source["id"]
    traverse = []
    traverse_hashes = {}
    traverse_files = meta.get("traverse_files", [])
    assert len(traverse_files) == len(set(traverse_files))
    if meta.get("traverse_files_gzip"):
        assert meta["traverse_files_gzip"] == [file + ".gz" for file in traverse_files]
    for file in traverse_files:
        path = DIST / file
        raw = path.read_bytes()
        if meta.get("traverse_files_gzip"):
            assert gzip.decompress(Path(str(path) + ".gz").read_bytes()) == raw, path
        chunk = json.loads(raw)
        assert isinstance(chunk, list) and chunk, path
        traverse.extend(chunk)
        traverse_hashes[file] = hashlib.sha256(raw).hexdigest()
    assert len(traverse) == meta["traverse_point_count"]
    route_by_key = defaultdict(set)
    for loc in traverse:
        assert all(isinstance(loc[k], (float, int)) and math.isfinite(loc[k]) for k in ("lat", "lon"))
        assert -90 <= loc["lat"] <= 90 and -360 <= loc["lon"] <= 360, loc
        assert all(isinstance(loc[k], int) and loc[k] >= 0 for k in ("site", "drive")), loc
        if loc.get("source_id"):
            assert loc["source_id"] in source_ids, loc["source_id"]
        route_by_key[loc["site"], loc["drive"]].add((loc["lat"], loc["lon"]))
    location_count, calibration_count = 0, 0
    original_rows = set()
    for p in points:
        assert COMMON.issubset(p["oxides"]), p["id"]
        assert isinstance(p["sol"], int) and p["sol"] >= 0, p["id"]
        assert isinstance(p["is_calibration"], bool), p["id"]
        calibration_count += p["is_calibration"]
        for section in [p["oxides"], p["uncertainty"]["rmsep"], p["uncertainty"]["shot_sd"]]:
            assert all(v is None or isinstance(v, (float, int)) and math.isfinite(v) for v in section.values()), p["id"]
        if p.get("source_id"):
            assert p["source_id"] in source_ids, p["source_id"]
        if name == "supercam":
            provenance = p["provenance"]
            assert provenance["source_table_id"] in source_ids
            assert provenance["masterlist_source_id"] in source_ids
            rows = provenance["source_rows"]
            assert rows and len(set(rows)) == len(rows)
            assert all(isinstance(row, int) and row > 0 for row in rows)
            assert not original_rows.intersection(rows), "source row assigned to multiple measurements"
            original_rows.update(rows)
            assert provenance["source_row"] in rows
            assert provenance["source_version"] == meta["archive_version"]
        if p.get("location"):
            loc = p["location"]
            assert "rover" in loc["kind"], loc
            assert -90 <= loc["lat"] <= 90 and -360 <= loc["lon"] <= 360, loc
            assert all(math.isfinite(loc[k]) for k in ["lat", "lon"])
            assert (loc["site"], loc["drive"]) == (p["site"], p["drive"])
            assert (loc["lat"], loc["lon"]) in route_by_key[loc["site"], loc["drive"]], p["id"]
            location_count += not p["is_calibration"]
    matched_spots, unmatched_spots = 0, 0
    for target in meta["rmi_targets"]:
        image = DIST / target["image_local"]
        assert image.is_file(), image
        assert hashlib.sha256(image.read_bytes()).hexdigest() == target["display_image_sha256"]
        for spot in target["points"]:
            assert 0 <= spot["x"] <= target["width"] and 0 <= spot["y"] <= target["height"]
            if spot["point_id"] is None:
                assert not spot["has_composition"]
                unmatched_spots += 1
                continue
            p = indexed[spot["point_id"]]
            assert p["sol"] == target["sol"], (p["id"], target["id"])
            assert target["id"] in p["rmi"], (p["id"], target["id"])
            matched_spots += 1
    if name == "chemcam":
        p = indexed["CL5_399178818CCS_F0030078CCAM01019P3"]
        assert (p["target"], p["sol"], p["oxides"]["SiO2"], p["uncertainty"]["rmsep"]["SiO2"], p["uncertainty"]["shot_sd"]["SiO2"]) == ("Mara_1", 19, 51.5, 5.0, 0.5)
    summary = meta["summary"]
    science = [point for point in points if not point["is_calibration"]]
    expected = {
        "point_count" if name == "chemcam" else "points": len(points),
        "science_point_count" if name == "chemcam" else "science_points": len(science),
        "calibration_point_count" if name == "chemcam" else "calibration_points": calibration_count,
        "geolocated_science_point_count" if name == "chemcam" else "geolocated_science_points": location_count,
        "min_sol" if name == "chemcam" else "sol_min": min(point["sol"] for point in points),
        "max_sol" if name == "chemcam" else "sol_max": max(point["sol"] for point in points),
        "target_count" if name == "chemcam" else "target_sequences": len({(point["sol"], point["sequence"], point["target"]) for point in science}),
        "rmi_target_count" if name == "chemcam" else "rmi_targets": len(meta["rmi_targets"]),
        "rmi_point_count" if name == "chemcam" else "rmi_annotation_points": matched_spots + unmatched_spots,
        "quality_flag_counts": dict(Counter(flag for point in points for flag in point["quality_flags"])),
    }
    if name == "chemcam":
        moc_sources = [source for source in meta["sources"] if re.fullmatch(r"moc_\d+_\d+\.csv", source["id"])]
        assert sum(source["rows"] for source in moc_sources) == len(points)
        assert all(source["rows"] == source["declared_rows"] for source in moc_sources)
        expected.update(moc_file_count=len(moc_sources),
                        unlocated_science_point_count=len(science) - location_count,
                        geolocated_science_location_count=len({(point["site"], point["drive"]) for point in science if point["location"]}))
    else:
        expected.update(source_rows=len(original_rows),
                        exact_duplicate_source_rows_collapsed=len(original_rows) - len(points),
                        geolocated_points=sum(point["location"] is not None for point in points),
                        rmi_points_with_composition=matched_spots,
                        metadata_joins=dict(Counter(point["provenance"]["metadata_join"] for point in points)),
                        location_sources=dict(Counter(point["location"]["source_id"] for point in points if point["location"])))
    for key, value in expected.items():
        assert summary[key] == value, (name, key, summary[key], value)
    result = {"mission": name, "measurements": len(points),
              "science_measurements": len(points) - calibration_count,
              "calibration_measurements": calibration_count,
              "geolocated_science_measurements": location_count,
              "sol_min": min(p["sol"] for p in points),
              "sol_max": max(p["sol"] for p in points),
              "rmi_images": len(meta["rmi_targets"]),
              "rmi_matched_spots": matched_spots,
              "rmi_unmatched_spots": unmatched_spots,
              "traverse_points": len(traverse),
              "traverse_chunk_sha256": traverse_hashes,
              "checks": "passed"}
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    results = [validate(name) for name in ["chemcam", "supercam"]]
    (ROOT / "VALIDATION.json").write_text(json.dumps(results, indent=2) + "\n")
