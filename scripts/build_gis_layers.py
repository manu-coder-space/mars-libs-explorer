#!/usr/bin/env python3
"""Build the pinned Mar-to-gis Jezero display layers from USGS SIM3464.

Only the Python standard library is required.  This script does not update the
rover measurements or assert revised geological interpretations.  The output
uses Mars geographic degrees, NOT RFC 7946's Earth/WGS84 coordinates; the Mars
coordinate-system foreign member must accompany any exported geometries.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request


SERVICE = "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Jezero_FeatureServiceFromPro/FeatureServer"
SOURCE_URL = "https://doi.org/10.3133/sim3464"
PUBLICATION_URL = "https://www.usgs.gov/maps/geologic-map-jezero-crater-and-nili-planum-region-mars"
SOURCE_ID = "jezero_sim3464"
RADIUS_M = 3396190.0
DEGREE_M = RADIUS_M * math.pi / 180.0
KINDS = {
    "channel (fluvial)": "channel",
    "crest of crater rim": "crater_rim",
    "crest of buried crater": "buried_crater",
    "ridge crest (type 1), certain": "ridge_crest",
    "lineament": "lineament",
    "delta lobe front": "delta_front",
}


def encoded(doc):
    return (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, path, refresh=False):
    if refresh or not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            raw = response.read()
        parsed = json.loads(raw)
        if "error" in parsed:
            raise RuntimeError(f"Source returned an error: {parsed['error']}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    raw = path.read_bytes()
    parsed = json.loads(raw)
    if "error" in parsed:
        raise RuntimeError(f"Invalid cached response: {path}")
    return parsed, {"url": url, "sha256": sha(raw), "bytes": len(raw)}


def simplify_path(points, tolerance_m=2.0):
    """Douglas-Peucker in a local Mars metric plane; retain original vertices.

    A 2 m tolerance is a display simplification, not a claim of 2 m mapping
    accuracy.  The original map is 1:75,000.  No coordinates are interpolated.
    """
    if len(points) < 3 or tolerance_m <= 0:
        return points
    center_lat = sum(p[1] for p in points) / len(points)
    sx = DEGREE_M * math.cos(math.radians(center_lat))
    sy = DEGREE_M
    xy = [(p[0] * sx, p[1] * sy) for p in points]
    keep = {0, len(points) - 1}
    todo = [(0, len(points) - 1)]
    tolerance2 = tolerance_m * tolerance_m
    while todo:
        first, last = todo.pop()
        ax, ay = xy[first]
        bx, by = xy[last]
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        farthest, distance2 = -1, tolerance2
        for i in range(first + 1, last):
            px, py = xy[i]
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2)) if length2 else 0.0
            d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > distance2:
                farthest, distance2 = i, d2
        if farthest >= 0:
            keep.add(farthest)
            todo.extend(((first, farthest), (farthest, last)))
    return [points[i] for i in sorted(keep)]


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=root / ".cache" / "gis-lines")
    parser.add_argument("--output", type=Path, default=root / "dist" / "Mar-to-gis" / "data")
    parser.add_argument("--refresh", action="store_true", help="Fetch current source responses instead of using cached snapshots")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    features, retrievals, omitted, input_counts, original_points, output_points = [], [], [], {}, 0, 0
    source_wkt = None
    for layer_id in (5, 6):
        metadata, record = fetch(f"{SERVICE}/{layer_id}?f=json", args.cache / f"layer-{layer_id}-metadata.json", args.refresh)
        retrievals.append(record)
        source_wkt = metadata["extent"]["spatialReference"]["wkt"]
        offset, source_features = 0, []
        while True:
            query = urllib.parse.urlencode({"where": "1=1", "outFields": "*", "outSR": "104971", "f": "json", "returnGeometry": "true", "geometryPrecision": "6", "resultRecordCount": "2000", "resultOffset": str(offset), "orderByFields": "OBJECTID ASC"})
            page, record = fetch(f"{SERVICE}/{layer_id}/query?{query}", args.cache / f"layer-{layer_id}-page-{offset}.json", args.refresh)
            if page.get("spatialReference", {}).get("wkid") != 104971:
                raise ValueError("The service did not return the requested Mars geographic CRS")
            retrievals.append(record)
            source_features.extend(page["features"])
            if not page.get("exceededTransferLimit"):
                break
            if not page["features"]:
                raise ValueError("Empty page with transfer limit flag")
            offset += len(page["features"])
        input_counts[str(layer_id)] = len(source_features)
        for source_feature in source_features:
            attributes = source_feature["attributes"]
            raw_paths = source_feature.get("geometry", {}).get("paths", [])
            paths = [p for p in raw_paths if len(p) >= 2]
            if not paths:
                omitted.append({"source_layer_id": layer_id, "source_object_id": attributes["OBJECTID"], "reason": "Source record has no drawable geometry", "original_attributes": attributes})
                continue
            label = attributes["TYPE"]
            if layer_id == 6 and label not in KINDS:
                raise ValueError(f"Unreviewed source line classification: {label}")
            original_points += sum(map(len, paths))
            # Contacts are the large source layer. Linear features are retained
            # exactly as supplied at the requested six-decimal precision.
            if layer_id == 5:
                paths = [simplify_path(p) for p in paths]
            output_points += sum(map(len, paths))
            geometry = {"type": "LineString", "coordinates": paths[0]} if len(paths) == 1 else {"type": "MultiLineString", "coordinates": paths}
            features.append({"type": "Feature", "id": f"sim3464-{layer_id}-{attributes['OBJECTID']}", "properties": {"kind": "contact" if layer_id == 5 else KINDS[label], "label": label, "source_id": SOURCE_ID, "source_url": SOURCE_URL, "source_layer_id": layer_id, "source_object_id": attributes["OBJECTID"], "map_scale": "1:75,000", "map_year": 2020, "original_attributes": attributes}, "geometry": geometry})

    coordinate_system = {"body": "Mars", "name": "Mars_2000_Sphere", "esri_wkid": 104971, "sphere_radius_m": RADIUS_M, "latitude_type": "planetocentric", "longitude_direction": "east", "coordinate_order": ["longitude", "latitude"], "units": "degrees", "not_earth_wgs84": True}
    collection = {"type": "FeatureCollection", "name": "USGS SIM3464 Jezero contacts and linear features — display edition", "coordinate_system": coordinate_system, "source_id": SOURCE_ID, "source_url": SOURCE_URL, "features": features}
    raw = encoded(collection)
    (args.output / "jezero-lines.geojson").write_bytes(raw)
    source = {"id": SOURCE_ID, "title": "Geologic map of Jezero crater and the Nili Planum region, Mars", "authors": ["Vivian Z. Sun", "Kathryn M. Stack"], "year": 2020, "series": "USGS Scientific Investigations Map 3464", "doi": "10.3133/sim3464", "url": SOURCE_URL, "publication_url": PUBLICATION_URL, "official_gis_download_page": "https://pubs.usgs.gov/sim/3464/", "web_map": "https://usgs.maps.arcgis.com/apps/webappviewer/index.html?id=a0ae4b521f7a4a6ca2cf0f0c551d5293", "service_url": SERVICE, "publication_scale": "1:75,000", "native_crs_wkt": source_wkt, "display_coordinate_system": coordinate_system, "license": "USGS public-domain map; hosted web service is provided for viewing purposes", "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "retrievals": retrievals, "input_feature_counts_by_layer": input_counts, "display_feature_count": len(features), "display_counts_by_kind": dict(Counter(f["properties"]["kind"] for f in features)), "display_counts_by_original_label": dict(Counter(f["properties"]["label"] for f in features)), "omitted_records": omitted, "processing": {"service_reprojection": "Native Mars Transverse Mercator, central meridian 77.5E, to ESRI:104971 via service outSR", "source_coordinate_precision_decimal_places": 6, "contact_display_simplification": "Douglas-Peucker with 2 m tolerance in local Mars equirectangular metric coordinates; original retained vertices only", "linear_feature_simplification": "None beyond service six-decimal output precision", "original_coordinate_count": original_points, "display_coordinate_count": output_points, "clipped": False}, "limits": ["This is a pre-landing 2020 orbital interpretation. Display with its publication date and source map scale.", "The hosted source map is provided for viewing. Use the linked official GIS/PDF for publication-grade spatial analysis.", "Lineaments, ridge crests, channels, crater rims and delta fronts are the source classifications; they are not collectively tectonic faults.", "The contact whose label is boundary is the artificial map frame, not a geological boundary.", "Rover locations are measurement-position proxies. A spatial overlap does not demonstrate that the remotely sampled rock belongs to that mapped unit.", "Coordinate precision and display simplification are not position-accuracy estimates. Mars coordinates must not be assigned an Earth/WGS84 CRS."]}
    all_positions = [p for f in features for path in ([f["geometry"]["coordinates"]] if f["geometry"]["type"] == "LineString" else f["geometry"]["coordinates"]) for p in path]
    actual_bounds = [min(p[0] for p in all_positions), min(p[1] for p in all_positions), max(p[0] for p in all_positions), max(p[1] for p in all_positions)]
    manifest = {"schema_version": 1, "sources": [source], "layers": [{"id": "jezero-lines", "mission": "supercam", "file": "jezero-lines.geojson", "source_id": SOURCE_ID, "feature_count": len(features), "sha256": sha(raw), "bytes": len(raw), "bounds": actual_bounds, "nominal_map_bounds": [76.8, 17.7, 77.8, 18.7], "coordinate_system": coordinate_system}]}
    (args.output / "sources.json").write_bytes(encoded(manifest))
    print(json.dumps({"features": len(features), "counts": source["display_counts_by_kind"], "omitted": len(omitted), "bytes": len(raw), "original_coordinates": original_points, "display_coordinates": output_points, "sha256": sha(raw)}))


if __name__ == "__main__":
    main()
