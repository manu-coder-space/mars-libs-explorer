#!/usr/bin/env python3
"""Bundle validated mission ingest outputs for a portable static website.

This is a packaging step. It does not alter the chemistry or infer positions.
Run from any directory: python scripts/assemble_data.py --input-root PATH
PATH must contain chemcam/data.json and supercam/data.json plus their images.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def bundle_mission(name, input_root, output_root, limit=6_000_000):
    source_dir = input_root / name
    source = source_dir / "data.json"
    data = json.loads(source.read_text())
    points = data.pop("points")
    if not points:
        raise ValueError(f"{name}: no measurements")
    ids = {p["id"] for p in points}
    if len(ids) != len(points):
        raise ValueError(f"{name}: duplicate measurement identifiers")
    chunks_dir = output_root / "data" / name
    chunks_dir.mkdir(parents=True, exist_ok=True)
    # The UI displays measurement-linked positions. Preserve the complete
    # official traverses separately, without loading them on every visit.
    traverse = data.pop("traverse", [])
    data["traverse_files"] = []
    data["traverse_files_gzip"] = []
    for old in chunks_dir.glob("traverse-*.json*"):
        old.unlink()
    for start in range(0, len(traverse), 5000):
        path = chunks_dir / f"traverse-{start // 5000 + 1:03d}.json"
        content = encoded(traverse[start:start + 5000])
        path.write_bytes(content)
        path.with_suffix(".json.gz").write_bytes(gzip.compress(content, compresslevel=9, mtime=0))
        data["traverse_files"].append(path.relative_to(output_root).as_posix())
        data["traverse_files_gzip"].append(path.relative_to(output_root).as_posix() + ".gz")
    data["traverse_point_count"] = len(traverse)
    files, gzip_files, files_provenance = [], [], []
    # Remove only this script's previous generated chunks, not unrelated files.
    for old in chunks_dir.glob("points-*.json*"):
        old.unlink()
    buffer, size = [], 2

    def flush():
        nonlocal buffer, size
        if not buffer:
            return
        blob = b"[" + b",".join(buffer) + b"]"
        filename = f"points-{len(files)+1:03d}.json"
        path = chunks_dir / filename
        path.write_bytes(blob)
        compressed = gzip.compress(blob, compresslevel=9, mtime=0)
        path.with_suffix(".json.gz").write_bytes(compressed)
        rel = path.relative_to(output_root).as_posix()
        files.append(rel)
        gzip_files.append(rel + ".gz")
        files_provenance.append({"file": rel, "point_count": len(buffer),
                                 "sha256": hashlib.sha256(blob).hexdigest(),
                                 "bytes": len(blob), "gzip_bytes": len(compressed)})
        buffer, size = [], 2

    for point in points:
        blob = encoded(point)
        if buffer and size + len(blob) + 1 > limit:
            flush()
        buffer.append(blob)
        size += len(blob) + 1
    flush()

    sources = data.get("sources", [])
    if isinstance(sources, dict):
        sources = [dict(value, id=key) for key, value in sources.items()]
    data["sources"] = sources
    assets = output_root / "assets" / name
    assets.mkdir(parents=True, exist_ok=True)
    for target in data.get("rmi_targets", []):
        local = target.get("display_image_local_path") or target.get("image_local_path") or target.get("image_local")
        if not local:
            raise ValueError(f"{name}/{target['id']}: missing local RMI image")
        candidate = Path(local)
        if not candidate.is_absolute():
            candidate = source_dir / candidate
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        dest = assets / candidate.name
        shutil.copy2(candidate, dest)
        relative = dest.relative_to(output_root).as_posix()
        target["image_local"] = relative
        target["image_local_path"] = relative
        target["display_image_local_path"] = relative
        target["display_image_sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
        for spot in target["points"]:
            identifier = spot.get("point_id", spot.get("id"))
            if identifier is not None and identifier not in ids:
                raise ValueError(f"{name}: RMI references unknown measurement {identifier}")
            spot["point_id"] = identifier
            spot["point"] = spot.get("point", spot.get("number"))
            spot["has_composition"] = identifier is not None
            if not (0 <= spot["x"] <= target["width"] and 0 <= spot["y"] <= target["height"]):
                raise ValueError(f"{name}: RMI point outside image")
    data["point_files"] = files
    data["point_files_gzip"] = gzip_files
    data["packaging"] = {"source_data_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                         "point_count": len(points), "chunks": files_provenance,
                         "chemistry_modified": False}
    destination = output_root / "data" / f"{name}.json"
    destination.write_bytes(encoded(data))
    print(json.dumps({"mission": name, "points": len(points), "chunks": len(files),
                      "uncompressed_bytes": sum(x["bytes"] for x in files_provenance),
                      "gzip_bytes": sum(x["gzip_bytes"] for x in files_provenance),
                      "rmi_images": len(data.get("rmi_targets", []))}))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=ROOT / "scripts")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--mission", choices=["both", "chemcam", "supercam"], default="both")
    args = parser.parse_args()
    for mission in (["chemcam", "supercam"] if args.mission == "both" else [args.mission]):
        bundle_mission(mission, args.input_root.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
