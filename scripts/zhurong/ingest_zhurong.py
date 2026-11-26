#!/usr/bin/env python3
"""Import openly downloadable, author-published MarSCoDe LIBS and SWIR data.

Uses only Python's standard library. The XLSX sources are read as OOXML; no
workbooks are created or edited. Source values, units and missingness are kept.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
FILES = [
    ("luo_s1", "8402478", "Data Set S1.xlsx", "luo_s1.xlsx", "8786a2025e733702f1a80bce6b9912ae"),
    ("luo_s2", "8402478", "Data Set S2.xlsx", "luo_s2.xlsx", "f311edfbb6c6427a41d72c46021cbfe2"),
    ("luo_s3", "8402478", "Data Set S3.xlsx", "luo_s3.xlsx", "5fb85d2349dbb1c513644bde36518894"),
    ("zhang_volatiles_s1", "11480713", "Supplemental data 1.xlsx", "zhang_volatiles_s1.xlsx", "b68c49a48045f43fecc601dd40961c34"),
    ("zhang_volatiles_s2", "11480713", "Supplemental data 2.xlsx", "zhang_volatiles_s2.xlsx", "e8e61eaa7170c61862d5f7b1c7cd07ce"),
    ("zhang_swir", "16809501", "SWIR.zip", "zhang_swir.zip", "4226796e93886b3bcb0c6199351b20a3"),
]


def workbook_rows(path: Path) -> list[dict]:
    """Read original cell values, with physical spreadsheet row numbers."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = ["".join(s.itertext()) for s in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("x:si", NS)]
        rows = []
        for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).findall("x:sheetData/x:row", NS):
            values = {}
            for cell in row.findall("x:c", NS):
                value = cell.find("x:v", NS)
                value = value.text if value is not None else ""
                if cell.get("t") == "s":
                    value = shared[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(cell.find("x:is", NS).itertext())
                values[re.sub(r"\d", "", cell.get("r"))] = value
            rows.append({"row": int(row.get("r")), "cells": values})
        return rows


def number(value):
    if value in (None, "", "——", "—", "–", "-"):
        return None
    return float(value)


def sol_from_label(label: str):
    match = re.match(r"(?:ZR|Sol)0*(\d+)", label, re.I)
    return int(match[1]) if match else None


def source_file(spec, source_dir, input_dir=None):
    sid, record, filename, local_name, md5 = spec
    path = source_dir / local_name
    url = "https://zenodo.org/api/records/" + record + "/files/" + urllib.parse.quote(filename) + "/content"
    if input_dir and (input_dir / filename).exists():
        path.write_bytes((input_dir / filename).read_bytes())
    elif not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
    content = path.read_bytes()
    if hashlib.md5(content).hexdigest() != md5:
        raise ValueError(f"Published MD5 mismatch for {filename}")
    return {
        "id": sid,
        "title": filename,
        "url": url,
        "record_url": f"https://zenodo.org/records/{record}",
        "doi": f"10.5281/zenodo.{record}",
        "license": "CC BY 4.0",
        "local_path": f"data/zhurong_sources/{local_name}",
        "md5": md5,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, help="Optional folder with original downloaded filenames")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/data/zhurong.json")
    args = parser.parse_args()
    source_dir = args.output.parent / "zhurong_sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    files = [source_file(spec, source_dir, args.input_dir) for spec in FILES]
    file_by_id = {f["id"]: f for f in files}

    tables = []
    titles = {
        "luo_s1": "Li and major-element peak areas",
        "luo_s2": "Sr and major-element peak areas",
        "luo_s3": "S and major-element peak areas",
        "zhang_volatiles_s1": "H, S and Cl fitted peaks",
        "zhang_volatiles_s2": "Major-element peaks in sulfur-bearing rocks",
    }
    for spec in FILES[:5]:
        sid, _, _, filename, _ = spec
        sheet = workbook_rows(source_dir / filename)
        luo = sid.startswith("luo_")
        header_row = 2 if luo else 1
        headers = next(r["cells"] for r in sheet if r["row"] == header_row)
        keys = [c for c in headers if c != "A" and not (sid == "zhang_volatiles_s1" and c == "B")]
        columns = []
        for c in keys:
            label = headers[c]
            unit = "normalized peak area"
            if sid == "zhang_volatiles_s1":
                unit = ("dimensionless" if "r2" in label else
                        "normalized peak area" if "normed" in label else
                        "source FWHM units" if "FWHM" in label else "source peak-area units")
            columns.append({"key": c, "label": label, "unit": unit})
        data_rows = []
        for row in sheet:
            cells = row["cells"]
            target = cells.get("A", "")
            if row["row"] <= header_row or not target:
                continue
            values = {c: number(cells.get(c)) for c in keys}
            data_rows.append({
                "id": sid + ":" + target,
                "target": target,
                "target_type": cells.get("B") if sid == "zhang_volatiles_s1" else None,
                "sol": sol_from_label(target),
                "sol_basis": "parsed from published target label",
                "location": None,
                "values": values,
                "source_id": sid,
                "source_row": row["row"],
            })
        note = "Published normalized LIBS peak areas; these are not concentrations, wt% or mineral abundances."
        if sid in ("luo_s1", "luo_s2"):
            note += " The paper normalizes spectra by the integrated intensity of each instrument channel; Li uses VNIR and Sr uses VIS. The original Mg 518.51 column label is retained, although repository metadata says 518.15 nm."
        elif sid == "luo_s3":
            note += " The paper describes S 564 nm normalization to O 777 nm; do not compare its numeric scale with the Li/Sr tables."
        elif sid == "zhang_volatiles_s1":
            note = "Original fitted peak areas, goodness of fit, widths and normalized peak areas. Blank/dash cells mean not reported, not zero. H, S or Cl emission does not establish organic matter."
        tables.append({
            "id": sid, "title": titles[sid], "source_id": sid,
            "source_url": file_by_id[sid]["record_url"],
            "download_url": file_by_id[sid]["local_path"],
            "quantity": "published_LIBS_peak_fit" if sid == "zhang_volatiles_s1" else "normalized_LIBS_peak_area",
            "columns": columns, "rows": data_rows, "notes": note,
        })

    with zipfile.ZipFile(source_dir / "zhang_swir.zip") as z:
        csv_content = z.read("SWIR/SWIR_calibrated_spectra.csv")
        readme = z.read("SWIR/Readme.txt").decode("utf-8-sig").strip()
    (source_dir / "swir_calibrated_spectra.csv").write_bytes(csv_content)
    rows = list(csv.reader(io.StringIO(csv_content.decode("utf-8-sig"))))
    headers = rows[0]
    values = [[float(v) for v in row] for row in rows[1:] if row and row[0]]
    spectra = [{
        "id": "zhurong-swir:" + name,
        "target": name,
        "sol": sol_from_label(name),
        "sol_basis": "published column label",
        "reflectance": [row[i] for row in values],
        "location": None,
        "source_id": "zhang_swir",
        "source_column": i + 1,
    } for i, name in enumerate(headers[1:], start=1)]
    swir = {
        "quantity": "calibrated_reflectance",
        "unit": "dimensionless reflectance",
        "wavelength_nm": [row[0] for row in values],
        "spectra": spectra,
        "source_id": "zhang_swir",
        "source_url": "https://zenodo.org/records/16809501",
        "download_url": "data/zhurong_sources/swir_calibrated_spectra.csv",
        "processing": readme,
        "note": "These are short-wave infrared reflectance spectra, not Raman spectra. Mineral identifications require band analysis and reference spectra; the app does not automatically identify a mineral from a trough.",
    }

    # Merge only identical Luo target labels across the same author's tables.
    # The timestamp-based Zhang labels are retained separately; no unverified
    # cross-publication observation identity or geographic join is attempted.
    observations = {}
    for table in tables:
        for row in table["rows"]:
            identity = ("luo:" if table["id"].startswith("luo_") else "zhang:" + table["id"] + ":") + row["target"]
            obs = observations.setdefault(identity, {
                "id": "zhurong:" + identity, "mission": "Zhurong", "instrument": "MarSCoDe LIBS",
                "category": "libs_peak_measurement", "target": row["target"], "sol": row["sol"],
                "location": None, "oxides": None, "measurement_refs": [],
            })
            obs["measurement_refs"].append({"table_id": table["id"], "row_id": row["id"], "source_row": row["source_row"]})

    sources = files + [
        {"id": "luo2024", "title": "Luo et al. (2024), Alkali trace elements observed by MarSCoDe LIBS", "url": "https://doi.org/10.1029/2024JE008366"},
        {"id": "zhang2024", "title": "Zhang et al. (2024), Volatile elements characterized by MarSCoDe", "url": "https://doi.org/10.3847/1538-3881/ad6560"},
        {"id": "zhang2025", "title": "Zhang et al. (2025), In situ observation of weathering rinds", "url": "https://doi.org/10.1029/2025JE009196"},
        {"id": "liu2026", "title": "Liu et al. (2026), Primary evaporite in southern Utopia Planitia", "url": "https://doi.org/10.1038/s41550-026-02917-3"},
        {"id": "clpds", "title": "CNSA Lunar and Planetary Data Release System — Tianwen-1", "url": "https://clpds.bao.ac.cn/web/enmanager/mars1"},
    ]
    data = {
        "schema_version": "1.0",
        "mission": "Zhurong", "instrument": "MarSCoDe", "region": "Southern Utopia Planitia",
        "access_status": "public_author_supplements_imported_primary_archive_registration_required",
        "checked_date": "2026-11-16",
        "chemistry_available": False,
        "libs_peak_data_available": True,
        "swir_data_available": True,
        "raman_available": False,
        "overview": "Real Chinese rover LIBS peak measurements and calibrated SWIR spectra from author-published open datasets. Exact target coordinates and a verified per-target major-oxide table are not bundled.",
        "summary": {
            "libs_tables": len(tables),
            "libs_table_rows": sum(len(t["rows"]) for t in tables),
            "luo_unique_target_labels": len({r["target"] for t in tables[:3] for r in t["rows"]}),
            "volatile_target_rows": len(tables[3]["rows"]),
            "swir_spectra": len(spectra), "swir_wavelengths": len(values),
            "located_measurements": 0, "major_oxide_measurements": 0,
            "count_note": "Rows in different publications/tables may describe the same target; counts are not additive unique observations.",
        },
        "landing_context": {
            "lat": 25.066, "lon": 109.925,
            "kind": "approximate_landing_site_only",
            "latitude_convention": "not specified in cited coordinate statement",
            "source_id": "liu2026",
            "note": "Rounded published landing-site coordinates; not the position of any LIBS or SWIR target. Do not place the unlocated measurements here.",
        },
        "instrument_scope": "MarSCoDe combines LIBS, short-wave infrared spectroscopy and a microimaging camera. Its SWIR mineralogy data are a different measurement from Raman; no Chinese Mars Raman dataset is included.",
        "access": [
            {"title": "Imported open data", "status": "downloaded_and_verified", "description": "Five author-published LIBS spreadsheets and a calibrated SWIR archive were downloaded from Zenodo; original files, checksum verification and source rows are bundled.", "source_ids": ["luo_s1", "luo_s2", "luo_s3", "zhang_volatiles_s1", "zhang_volatiles_s2", "zhang_swir"]},
            {"title": "Primary Level 2B LIBS spectra", "status": "registration_required", "description": "Luo et al. state that CLPDS data are open after registration. No account-restricted primary spectra were downloaded for this version.", "url": "https://clpds.bao.ac.cn/web/enmanager/mars1", "source_ids": ["clpds", "luo2024"]},
            {"title": "Major-oxide and trace-concentration supplement", "status": "not_imported", "description": "Luo et al. Table S2 is listed by the publisher, but its public download returned HTTP 403 during this build. Peak ratios have not been converted to concentrations.", "url": "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024JE008366", "source_ids": ["luo2024"]},
        ],
        "interpretations": [
            {"title": "Gypsum-rich platy rocks", "evidence_status": "published_interpretation", "method": "LIBS + SWIR + imaging", "summary": "Liu et al. (2026) interpret platy rocks as a primary gypsum/selenite evaporite using crystal morphology, infrared absorptions and LIBS sulfur, hydrogen and calcium. This is mineralogical context, not an organic detection.", "source_id": "liu2026", "url": "https://doi.org/10.1038/s41550-026-02917-3", "location": None},
            {"title": "Weathering rinds", "evidence_status": "published_interpretation", "method": "SWIR + multispectral imaging", "summary": "Zhang et al. (2025) interpret spectra of some dark rock patches as consistent with silica-enriched leached rinds on basaltic glass. Dust cover and mixed fields of view affect interpretation.", "source_id": "zhang2025", "url": "https://doi.org/10.1029/2025JE009196", "location": None},
        ],
        "notes": [
            "Normalized LIBS peak area is a signal ratio, not elemental or oxide concentration. Numeric scales vary by line and processing method.",
            "Hydrogen, sulfur or chlorine peaks alone do not demonstrate organic molecules, habitability or life.",
            "Target labels and sol numbers are preserved. Different paper naming conventions have not been joined without an explicit identifier crosswalk.",
            "No continuous compositional field, organic region or exact target geography is inferred from these data.",
        ],
        "sources": sources, "peak_tables": tables, "swir": swir,
        "observations": list(observations.values()),
    }
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    manifest = {"checked_date": data["checked_date"], "sources": files, "summary": data["summary"]}
    (Path(__file__).parent / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "summary": data["summary"]}))


if __name__ == "__main__":
    main()
