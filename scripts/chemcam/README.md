# ChemCam data ingest

This directory contains a standard-library Python pipeline for NASA PDS ChemCam major-oxide composition (MOC) products. Python 3.10 or later is required. Paths are relative to the script directory, so the scripts can be copied to a repository without editing hard-coded paths.

## Reproduce

```bash
python scripts/chemcam/fetch_sources.py
python scripts/chemcam/ingest_chemcam.py
```

If running inside this directory, omit `scripts/chemcam/` from the commands. The first command discovers the public MOC tables, downloads their CSV and PDS3 labels, and downloads the official observation log and documentation. The second downloads the NASA rover-waypoint GeoJSON and ten selected RMI mosaic images/labels, then builds `data.json` and `qa_report.json`.

The current source snapshot is approximately 50 MB total: about 39 MB of tables, labels and context metadata plus 11 MB of selected RMI images. It does **not** download the full ChemCam spectral archive. Repeated runs reuse files whose cached SHA256 hashes match their sidecars.

To rebuild a completely cached snapshot without network requests:

```bash
python scripts/chemcam/ingest_chemcam.py --offline
```

To check for new or revised public source products explicitly:

```bash
python scripts/chemcam/fetch_sources.py --refresh
python scripts/chemcam/ingest_chemcam.py --refresh-context
```

Refresh requests use `If-None-Match` and `If-Modified-Since` where the server supplies those validators. New source data replace the corresponding cached files; their new hashes, retrieval times and versions are recorded. Keep the previous dataset/source-manifest snapshot if comparing release versions.

## Outputs

- `data.json`: full point records, oxide estimates, model prediction errors, shot variability, observation metadata, exact-join rover proxies, curated RMI coordinates, and source provenance.
- `source_manifest.json`: source URLs, bytes, SHA256, retrieval time, server validators and MOC product versions.
- `sample_record.json`: one actual Mara_1 record for interface integration.
- `qa_report.json`: source hash checks, per-table PDS label row-count checks, join completeness and representative checks.
- `findings.txt`: summary counts and interpretation constraints.
- `raw/`: original downloaded source files, each accompanied by a `.source.json` sidecar.

The full `data.json` is intended as a research/interchange dataset. The website build may create compact chunks and gzip files from it; source records remain traceable by `source_id` and `source_row`.

## Data conventions

Abundances are archived oxide weight percent, with the original totals. They are not normalized to 100%. `FeOT` means total iron expressed as FeO equivalent. `uncertainty.rmsep` and `uncertainty.shot_sd` remain distinct. RMSEP is not silently relabeled a confidence interval. No spectral quantification model is retrained or reapplied by this script.

`source_row` is the original CSV physical row number, counting its calibration-header lines. Observation-log metadata are joined by exact spacecraft clock. True acquisition sol is taken from that log, **not** inferred from the sequence-name suffix.

`is_calibration` uses explicit calibration terminology in the observation log: calibration, Cal Target or CCCT. The evidence is retained. A broad substring search for `cal` is deliberately avoided because it would also match geological descriptions such as calcium or vertical. These calibration points remain in the downloadable dataset and should be excluded from the website's default science selection.

## Geography

The official NASA MMGIS feed is:

https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json

Only an **exact site-and-drive join** is accepted. `location.kind` is `rover_position_proxy`: the coordinate is the rover position when observing, not the remote laser impact location. Target pointing and range are preserved as observing metadata but no target coordinate reconstruction is attempted. Unmatched records retain `location: null` and remain available for chemistry/sol analyses.

The raw feed does not specify a latitude convention in its GeoJSON. `latitude_convention` records that limitation rather than introducing an unsupported datum assumption. Elevation preserves the feed's `elev_geoid` field and is identified as such. The full rover route may extend beyond the chemistry archive's sol cutoff.

## RMI image coordinates

Each `rmi_targets` entry contains `image_local_path`, `image_url`, `label_url`, native `width` and `height`, and points with `point_id`, official annotation `point`, `x` and `y`. `point.rmi` contains matching RMI target IDs.

The coordinates come from `MSL:CCAM_ANNOTATION_VALUE` tuples in original PDS mosaic labels. They are applied directly to the original mosaic dimensions: x increases to the right, y increases down from the top of the image. The original source values are preserved without an invented subpixel correction. A visual check of Mara_1 confirms that the positions align with the official red annotation crosses. Source positioning uncertainty is not specified and remains `null`.

All selected images are original PNGs (roughly 0.77–1.53 MB each), with no resizing or cropping. To display an image at a smaller size, scale the image and overlay together using the same coordinate transform or SVG `viewBox`. The existing red crosses/numbers are part of the source PNG. The website may draw selectable chemistry markers above them; unsampled pixels must not be represented as measured chemistry.

Outside this RMI subset, `point` gives chronological observation order within a sequence and target. `point_index_kind` identifies this explicitly; it is not asserted to be an official raster point number.

## Quality flags

The original observation log's saturation, continuum, heterogeneity and ignore notes are preserved verbatim in `quality_notes`. An `archive_saturation_note` indicates the presence of a source note, not an automatic declaration that the composition is invalid. The same distinction applies to range, oxide-total and test-set boundary review flags. The website should make these flags inspectable and allow an explicit filtering choice.

The pipeline checks all 42 MOC table row counts against their labels, every cached file's hash, unique product identities, location join ambiguity, RMI coordinate bounds, the known Mara_1 composition and its uncertainties, and the classification of an actual onboard calibration-target observation.
