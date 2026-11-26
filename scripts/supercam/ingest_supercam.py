#!/usr/bin/env python3
"""Build a documented SuperCam point-composition dataset from public NASA PDS data.

Usage:
    python ingest_supercam.py [--workdir DIRECTORY] [--refresh]

Python 3 standard library is sufficient for the composition/position ingest.
Pillow, numpy and scipy are used only to extract official RMI annotation centers
and produce same-size JPEG display derivatives. No chemistry is interpolated.
Downloaded source files are cached in raw/; output data.json and data.json.gz
are portable. Source URLs, SHA-256 hashes and versions are in source_manifest.json.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

PDS = "https://pds-geosciences.wustl.edu/m2020/"
SUPER = PDS + "urn-nasa-pds-mars2020_supercam/"
PLACES = PDS + "urn-nasa-pds-mars2020_rover_places/data_localizations/"
OXIDES = ["SiO2", "TiO2", "Al2O3", "FeOT", "MgO", "CaO", "Na2O", "K2O"]
SOURCES = {
    "supercam_moc": ("supercam_libs_moc.csv", SUPER + "data_derived_spectra/supercam_libs_moc.csv"),
    "supercam_moc_label": ("supercam_libs_moc.xml", SUPER + "data_derived_spectra/supercam_libs_moc.xml"),
    "supercam_masterlist": ("m2020_scam_masterlist.csv", SUPER + "data_observation_log/m2020_scam_masterlist.csv"),
    "supercam_masterlist_label": ("m2020_scam_masterlist.xml", SUPER + "data_observation_log/m2020_scam_masterlist.xml"),
}
for _name in ("best_interp", "best_tactical", "telemetry"):
    SOURCES["places_" + _name] = (_name + ".csv", PLACES + _name + ".csv")
    SOURCES["places_" + _name + "_label"] = (_name + ".csv.xml", PLACES + _name + ".csv.xml")

RMI_SPECS = [
    {
        "id": "supercam-rmi-tselhchee-0015", "target": "Tselhchee", "sol": 15,
        "sequence": "scam15218", "order": "right_to_left", "expected_centers": 10,
        "name": "ascam_sol0015_scam15218_mos_fr08_aft_rgb_l___tselhchee____________p02",
        "notes": ["Masterlist and MOC use the spelling Tselchee; image label uses Tselhchee.",
                  "Point 4 is annotated in the image but has no row in the archived MOC table; it remains without composition."],
    },
    {
        "id": "supercam-rmi-iina-0028", "target": "Iina", "sol": 28,
        "sequence": "scam01028", "order": "right_to_left", "expected_centers": 10,
        "name": "ascam_sol0028_scam01028_mos_fr08_aft_rgb_lri_iina_________________p01",
        "notes": ["The source image also marks other SuperCam techniques; interactive chemistry uses only the red numbered LIBS crosshairs."],
    },
    {
        "id": "supercam-rmi-maaz-0012", "target": "Maaz", "sol": 12,
        "sequence": "scam15210", "order": "right_to_left", "expected_centers": 1,
        "name": "ascam_sol0012_scam15210_mos_fr08_aft_rgb_l_______________________p01",
        "notes": ["Single-spot LIBS observation; this image cannot supply a continuous rock-composition raster."],
    },
]


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def localtag(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def xml_values(path: Path, tag: str) -> list[str]:
    return [(n.text or "").strip() for n in ET.parse(path).getroot().iter() if localtag(n) == tag]


def finite(value: str | None) -> float | None:
    try:
        n = float(value or "")
        return n if math.isfinite(n) and n not in (-99999, -9999, -1e30) else None
    except (TypeError, ValueError):
        return None


def normalize_cdr(name: str) -> str:
    """Only remove the documented PDS file version suffix, preserving point ID."""
    name = name.strip().lower().split(":")[-1]
    return re.sub(r"p\d{2}\.fits$", "p", name)


def parse_cdr(name: str) -> dict:
    match = re.fullmatch(r"scam_(\d{4})_(\d{10})_(\d{3})_cl\d_(scam\d+)_(.*)_(\d{2,3})p", normalize_cdr(name))
    if not match:
        raise ValueError("Unrecognized MOC product ID: " + name)
    sol, sclk, fraction, sequence, target, point = match.groups()
    return {"sol": int(sol), "sclk": int(sclk), "fraction": fraction,
            "sequence": sequence, "target": target.strip("_"), "point": int(point)}


def master_key(row: dict) -> tuple:
    return (int(row["sol"]), row["seqid"].lower(), int(row["sclk"]), int(row["point_number"]))


class Cache:
    def __init__(self, folder: Path, refresh: bool):
        self.folder, self.refresh = folder, refresh
        self.raw = folder / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        manifest_path = folder / "source_manifest.json"
        old = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
        self.manifest = {item["id"]: item for item in old}

    def fetch(self, source_id: str, filename: str, url: str) -> Path:
        path = self.raw / filename
        previous = self.manifest.get(source_id, {})
        data = path.read_bytes() if path.exists() else None
        verified = data is not None and previous.get("url") == url and bool(previous.get("sha256"))
        if verified and sha256(data) != previous["sha256"]:
            raise ValueError("Cached source hash mismatch; remove the damaged cache file and retry: " + str(path))
        retrieved = previous.get("retrieved_at_utc")
        last_modified = previous.get("http_last_modified")
        etag = previous.get("http_etag")
        checked = previous.get("last_checked_at_utc")
        if self.refresh or not verified:
            headers = {"User-Agent": "Mars-LIBS-Atlas/1.0 (public-PDS-research)"}
            if verified:
                if etag:
                    headers["If-None-Match"] = etag
                if last_modified:
                    headers["If-Modified-Since"] = last_modified
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = response.read()
                    last_modified = response.headers.get("Last-Modified")
                    etag = response.headers.get("ETag")
                temporary = path.with_name(path.name + ".part")
                temporary.write_bytes(data)
                temporary.replace(path)
                retrieved = utcnow()
            except urllib.error.HTTPError as error:
                if error.code != 304 or not verified:
                    raise
            checked = utcnow()
        if data is None:
            raise ValueError("Source returned no verified bytes: " + url)
        entry = {"id": source_id, "url": url, "file": "raw/" + filename,
                 "bytes": len(data), "sha256": sha256(data), "retrieved_at_utc": retrieved}
        if last_modified:
            entry["http_last_modified"] = last_modified
        if etag:
            entry["http_etag"] = etag
        if checked:
            entry["last_checked_at_utc"] = checked
        if filename.endswith(".xml"):
            entry["version"] = xml_values(path, "version_id")[0]
            entry["logical_identifier"] = xml_values(path, "logical_identifier")[0]
        self.manifest[source_id] = entry
        print(f"Source {source_id}: {len(data):,} bytes", flush=True)
        return path

    def save(self):
        (self.folder / "source_manifest.json").write_text(json.dumps(list(self.manifest.values()), indent=2), encoding="utf-8")


def parse_places(paths: dict) -> tuple[dict, list]:
    """Use explicit PDS coordinates keyed by exact site/drive; never derive from IDs.

    Precedence: interpolated/corrected PLACES view, tactical view, then telemetry.
    All positions remain rover-location proxies rather than LIBS target coordinates.
    """
    location_by_key = {}
    for name in ("telemetry", "best_tactical", "best_interp"):
        sid = "places_" + name
        seen = set()
        with paths[sid].open(encoding="utf-8-sig", newline="") as handle:
            for source_row, row in enumerate(csv.DictReader(handle), start=2):
                if row["frame"] != "ROVER":
                    continue
                key = (int(row["site"]), int(row["drive"]))
                # Telemetry may have multiple poses: retain the latest sclk for a
                # site/drive, while corrected views are already one row per key.
                lat, lon = finite(row["planetocentric_latitude"]), finite(row["longitude"])
                if lat is None or lon is None or not (-90 <= lat <= 90 and 0 <= lon <= 360):
                    continue
                item = {"lat": lat, "lon": lon, "elevation_m": finite(row["elevation"]),
                        "northing_m": finite(row["northing"]), "easting_m": finite(row["easting"]),
                        "kind": "rover_position_proxy", "source": SOURCES[sid][1], "source_id": sid,
                        "source_row": source_row, "frame": "planetocentric_latitude_east_longitude",
                        "latitude_convention": "planetocentric", "longitude_convention": "positive_east_0_360",
                        "join": "exact_site_drive", "localization_sclk": int(row["sclk"]),
                        "localization_sol": int(row["sol"]), "site": key[0], "drive": key[1],
                        "position_uncertainty_m": None,
                        "target_offset_applied": False}
                if name == "telemetry" and key in seen and item["localization_sclk"] < location_by_key[key]["localization_sclk"]:
                    continue
                location_by_key[key] = item
                seen.add(key)
    # Route retains official positions. No spatial interpolation is added here.
    route = [dict(loc) for loc in location_by_key.values()
             if loc["localization_sclk"] > 0 and loc["localization_sol"] >= 0]
    route.sort(key=lambda x: x["localization_sclk"])
    return location_by_key, route


def extract_crosshairs(image_path: Path) -> list[tuple[int, int]]:
    """Extract centers of the red official annotation crosshairs, not rock features.

    Each cross uses red bars on a fixed 70-pixel separation. Some bar fragments
    are overwritten by other-technique circles in Iina. Their starting positions,
    seven-pixel widths and surviving cardinal pixels still identify each center.
    Numerals, logos and rock pixels cannot satisfy all four geometry conditions.
    """
    import numpy as np
    from PIL import Image
    from scipy.ndimage import label, find_objects
    pixels = np.asarray(Image.open(image_path).convert("RGB"))
    mask = (pixels[:, :, 0] > 150) & (pixels[:, :, 1] < 60) & (pixels[:, :, 2] < 60)
    labelled, _ = label(mask)
    vertical_x, horizontal = set(), []
    for component in find_objects(labelled):
        if component is None:
            continue
        ys, xs = component
        width, height = xs.stop - xs.start, ys.stop - ys.start
        if width == 7 and 10 <= height <= 37:
            vertical_x.add(xs.start + 3)
        elif 20 <= width <= 37 and height == 7:
            horizontal.append((xs.start, ys.start + 3))
    found = []
    horizontal = set(horizontal)
    for x in vertical_x:
        for xstart, y in horizontal:
            if xstart == x - 53 and (x + 17, y) in horizontal and y > 35 and y + 35 < mask.shape[0]:
                if mask[y - 35, x] and mask[y + 35, x] and mask[y, x - 35] and mask[y, x + 35]:
                    found.append((int(x), int(y)))
    return sorted(set(found))


def build_rmi(cache: Cache, records: list[dict]) -> list[dict]:
    from PIL import Image
    by_key = {(p["sol"], p["sequence"], p["point"]): p for p in records}
    output = []
    (cache.folder / "assets").mkdir(exist_ok=True)
    for spec in RMI_SPECS:
        urlbase = SUPER + f"data_special_rmi/sol_{spec['sol']:05d}/" + spec["name"]
        source_id = spec["id"] + "-png"
        png = cache.fetch(source_id, spec["name"] + ".png", urlbase + ".png")
        label_path = cache.fetch(spec["id"] + "-label", spec["name"] + ".xml", urlbase + ".xml")
        centers = extract_crosshairs(png)
        if len(centers) != spec["expected_centers"]:
            raise ValueError(f"RMI {spec['id']}: expected {spec['expected_centers']} crosshairs, found {len(centers)}")
        # Ordering was independently verified against visible point numerals on
        # each official annotation image. This is not a spatial extrapolation.
        centers.sort(key=lambda xy: xy[0], reverse=spec["order"] == "right_to_left")
        points = []
        for number, (x, y) in enumerate(centers, start=1):
            record = by_key.get((spec["sol"], spec["sequence"], number))
            if record:
                record["rmi"].append(spec["id"])
            points.append({"point_id": record["id"] if record else None, "point": number,
                           "x": x, "y": y, "has_composition": record is not None})
        image = Image.open(png).convert("RGB")
        display_name = "assets/" + spec["id"] + ".jpg"
        image.save(cache.folder / display_name, quality=92, subsampling=0, optimize=True)
        output.append({"id": spec["id"], "mission": "Perseverance", "instrument": "SuperCam",
                       "target": spec["target"], "sol": spec["sol"], "sequence": spec["sequence"],
                       "image_url": urlbase + ".png", "label_url": urlbase + ".xml",
                       "image_local_path": display_name, "original_local_path": "raw/" + png.name,
                       "source_id": source_id, "width": image.width, "height": image.height,
                       "coordinate_origin": "upper_left_zero_based",
                       "coordinate_method": "centers_of_official_PDS_annotation_crosshairs",
                       "coordinate_uncertainty_px": 1,
                       "coordinate_uncertainty_scope": "annotation_digitization_only; physical_laser_placement_uncertainty_not_specified",
                       "source_version": xml_values(label_path, "version_id")[0],
                       "display_derivative": "JPEG quality 92; original pixel dimensions retained; no resampling",
                       "notes": spec["notes"], "points": points})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--refresh", action="store_true", help="Check all sources with conditional requests against the verified cache")
    args = parser.parse_args()
    folder = args.workdir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    cache = Cache(folder, args.refresh)
    paths = {sid: cache.fetch(sid, filename, url) for sid, (filename, url) in SOURCES.items()}
    cache.save()

    with paths["supercam_moc"].open(encoding="utf-8-sig", newline="") as handle:
        moc_rows = list(csv.reader(handle))
    header_index = next(i for i, r in enumerate(moc_rows) if r and r[0] == "cdr_fname")
    header = moc_rows[header_index]
    meta = {r[0]: {oxide: finite(r[1 + 2*i]) for i, oxide in enumerate(OXIDES)}
            for r in moc_rows[1:header_index]}
    declared_records = int(xml_values(paths["supercam_moc_label"], "records")[0])
    archive_version = xml_values(paths["supercam_moc_label"], "version_id")[0]
    rows = [dict(zip(header, r)) for r in moc_rows[header_index + 1:] if any(r)]
    assert len(rows) == declared_records, (len(rows), declared_records)
    assert all(len(r) == len(header) for r in moc_rows[header_index + 1:] if any(r)), "Malformed MOC row"
    with paths["supercam_masterlist"].open(encoding="utf-8-sig", newline="") as handle:
        master_rows = list(csv.DictReader(handle))
    by_id, by_measurement = collections.defaultdict(list), collections.defaultdict(list)
    for source_row, row in enumerate(master_rows, start=2):
        if row["type"] != "LIBS":
            continue
        row = dict(row, source_row=source_row)
        by_id[normalize_cdr(row["cdr_fname"])].append(row)
        by_measurement[master_key(row)].append(row)
    locations, traverse = parse_places(paths)
    records = []
    seen_products = {}
    duplicate_rows_collapsed = 0
    join_counts = collections.Counter()
    sum_errors = []
    for index, values in enumerate(rows, start=header_index + 2):
        product_id = normalize_cdr(values["cdr_fname"])
        row_signature = tuple(values.get(column) for column in header)
        if product_id in seen_products:
            prior_signature, prior_record = seen_products[product_id]
            if row_signature != prior_signature:
                raise ValueError(f"Conflicting duplicate MOC values for {product_id}; manual scientific review required")
            prior_record["provenance"]["source_rows"].append(index)
            duplicate_rows_collapsed += 1
            continue
        parsed = parse_cdr(product_id)
        candidates = by_id[product_id]
        join = "exact_normalized_cdr_product_id"
        if not candidates:
            key = (parsed["sol"], parsed["sequence"], parsed["sclk"], parsed["point"])
            candidates = by_measurement[key]
            # Check fractional spacecraft clock as well; the first ten MOC rows
            # have target names in their IDs omitted in the current masterlist.
            candidates = [r for r in candidates if f"_{parsed['sclk']:010d}_{parsed['fraction']}_" in r["cdr_fname"]]
            join = "exact_sol_sequence_sclk_fraction_point; target_filename_alias"
        if len(candidates) != 1:
            raise ValueError(f"MOC row {index}: metadata join has {len(candidates)} candidates")
        row = candidates[0]
        join_counts[join] += 1
        oxides = {o: finite(values[o]) for o in OXIDES}
        shot_sd = {o: finite(values[o + "_stdev"]) for o in OXIDES}
        total = finite(values["Total"])
        assert all(v is not None for v in oxides.values()), f"Missing chemistry row {index}"
        assert all(v is not None and v >= 0 for v in shot_sd.values()), f"Invalid SD row {index}"
        target_type = row["Target_Type"].strip() or "Unknown"
        calibration = "scct" in target_type.lower() or "calibration" in target_type.lower() or row["targetname"].upper().startswith("SCCT")
        flags = []
        if calibration:
            flags.append("calibration_target")
        saturation = row["Saturation"].strip()
        if saturation and saturation.lower() not in ("no", "none", "false"):
            flags.append("archive_saturation_flag")
        comment = row["Comments"].strip()
        if comment:
            flags.append("archive_comment")
        if row["Moc Delivered"].strip().lower() == "no":
            flags.append("archive_delivery_status_conflict")
        outside = [o for o in OXIDES if not (meta["Min"][o] <= oxides[o] <= meta["Max"][o])]
        if outside:
            flags.append("outside_training_range")
        if any(v < 0 for v in oxides.values()):
            flags.append("negative_oxide_estimate")
        error = abs(sum(oxides.values()) - total)
        sum_errors.append(error)
        if error > 0.1:
            flags.append("reported_total_differs_from_oxide_sum")
        # This review band is a display heuristic, not an official rejection rule.
        if total < 80 or total > 120:
            flags.append("oxide_total_outside_80_120_review_band")
        match = re.search(r"EL\d__(\d{3})(\d{4})", row["edr_fname"])
        if not match:
            raise ValueError("Unrecognized EDR site/drive fields: " + row["edr_fname"])
        site, drive = map(int, match.groups())
        location = locations.get((site, drive))
        distance = finite(values["distance_mm"])
        distance = distance / 1000 if distance is not None else None
        record = {"id": "supercam:" + product_id, "mission": "Perseverance", "instrument": "SuperCam",
                  "sol": parsed["sol"], "sequence": parsed["sequence"], "point": parsed["point"],
                  "point_index_kind": "mission_raster_point_number",
                  "target": row["targetname"].strip() or parsed["target"], "target_type": target_type,
                  "is_calibration": calibration, "distance_m": distance, "oxides": oxides,
                  "uncertainty": {"rmsep": meta["RMSEP"], "shot_sd": shot_sd},
                  "total_wt_pct": total, "spectrum_total": finite(values["Tot.Em."]),
                  "sclk": parsed["sclk"], "site": site, "drive": drive,
                  "quality_flags": flags, "out_of_training_oxides": outside,
                  "archive_saturation": saturation or None, "archive_comment": comment or None,
                  "archive_moc_delivered": row["Moc Delivered"].strip() or None,
                  "location": dict(location) if location else None, "rmi": [],
                  "provenance": {"source_table_id": "supercam_moc", "source_row": index,
                                 "source_rows": [index],
                                 "source_version": archive_version,
                                 "moc_product_id": product_id, "masterlist_source_id": "supercam_masterlist",
                                 "masterlist_row": row["source_row"], "metadata_join": join,
                                 "cdr_filename": row["cdr_fname"], "edr_filename": row["edr_fname"]}}
        records.append(record)
        seen_products[product_id] = (row_signature, record)
    assert len({p["id"] for p in records}) == len(records), "Duplicate point IDs"
    records.sort(key=lambda p: (p["sol"], p["sclk"], p["point"]))
    rmi_targets = build_rmi(cache, records)
    cache.save()
    summary = {
        "source_rows": len(rows), "exact_duplicate_source_rows_collapsed": duplicate_rows_collapsed,
        "points": len(records), "science_points": sum(not p["is_calibration"] for p in records),
        "calibration_points": sum(p["is_calibration"] for p in records),
        "geolocated_points": sum(p["location"] is not None for p in records),
        "geolocated_science_points": sum(p["location"] is not None and not p["is_calibration"] for p in records),
        "target_sequences": len({(p["sol"], p["sequence"], p["target"]) for p in records if not p["is_calibration"]}),
        "sol_min": min(p["sol"] for p in records), "sol_max": max(p["sol"] for p in records),
        "rmi_targets": len(rmi_targets), "rmi_points_with_composition": sum(len(p["rmi"]) for p in records),
        "rmi_annotation_points": sum(len(t["points"]) for t in rmi_targets),
        "metadata_joins": dict(join_counts),
        "location_sources": dict(collections.Counter(p["location"]["source_id"] for p in records if p["location"])),
        "quality_flag_counts": dict(collections.Counter(f for p in records for f in p["quality_flags"])),
        "max_absolute_total_sum_difference_wt_pct": max(sum_errors),
    }
    notes = [
        "Values are archived team-derived major-oxide estimates in wt%; raw intensities are not treated as concentrations.",
        "FeOT denotes total iron expressed as FeO; it does not establish oxidation state or mineral identity.",
        "Reported oxide totals are retained and are not renormalized to 100 wt%.",
        "RMSEP is copied from the MOC table header and describes calibration prediction error; shot SD is a separate variability measure, not an interchangeable accuracy estimate.",
        "One row is one LIBS analysis point, usually an average of multiple shots. Repeated shots are not independent spatial pixels.",
        "Positions are explicit NASA PDS PLACES rover positions joined on exact site and drive. They are rover-position proxies, not reconstructed laser-hit coordinates.",
        "PLACES coordinate priority is best_interp, then best_tactical, then telemetry. No latitude or longitude is inferred from the site/drive numbers.",
        "A missing exact localization remains null. No spatial interpolation or extrapolation is added by this application.",
        "Onboard calibration targets are retained for provenance and flagged; exclude is_calibration=true from Mars-ground maps by default.",
        "The 80–120 wt% total review band is an application heuristic, not a PDS quality grade or automatic rejection rule.",
        "RMI coordinates are digitized centers of official annotation crosshairs. The one-pixel uncertainty concerns digitization only, not the physical LIBS footprint placement.",
        "Target names may have aliases or spelling revisions; joins use instrument observation identifiers rather than names alone.",
        "Identical repeated MOC rows with the same product ID are represented once; all original row numbers are retained in provenance.source_rows. Conflicting duplicates stop the ingest for review.",
    ]
    result = {"schema_version": "1.0", "mission": "Perseverance", "instrument": "SuperCam",
              "generated_at_utc": utcnow(), "archive_version": archive_version,
              "oxides": OXIDES, "units": {"oxides": "wt%", "distance_m": "m"},
              "summary": summary, "calibration_metadata": meta, "notes": notes,
              "sources": list(cache.manifest.values()), "points": records,
              "rmi_targets": rmi_targets, "traverse": traverse}
    encoded = json.dumps(result, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    (folder / "data.json").write_bytes(encoded)
    (folder / "data.json.gz").write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
