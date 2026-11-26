# SuperCam data ingest

Run `python -m pip install -r requirements.txt` from the project root to install
Pillow, NumPy and SciPy, then:

```bash
python scripts/supercam/ingest_supercam.py
```

The script uses its own directory as the default working directory. Pass
`--workdir PATH` for a different cache/output directory. Pass `--refresh` to
download fresh versions rather than reuse the cached original files. It writes
`data.json`, `data.json.gz`, a source manifest, summary and three same-size JPEG
display derivatives. The website ships with the completed results; refreshing
is optional and requires access to the public NASA PDS server.

The snapshot contains 12,121 unique points from 12,130 MOC rows. Nine exact
duplicate rows are represented once, with original row numbers in
`provenance.source_rows`. Conflicting duplicates stop the ingest. Calibration
targets are retained and flagged. Geography is an exact site/drive join to
published PLACES rover coordinates; the priority is best_interp, best_tactical,
then telemetry. These remain rover-position proxies.

RMI coordinates are centers of the instrument team's published annotations,
extracted from the actual annotation pixels. The one-pixel uncertainty describes
digitization, not physical targeting accuracy. Tselhchee annotation #4 has no
archived MOC row and receives no chemical estimate. MOC spells this target
Tselchee; identity is checked using observation identifiers.

The included `verification_report.json` records checks of every original source
hash, point chemistry, standard deviation, total, distance and localization,
plus RMI coordinates and gzip integrity. Raw cache files are excluded from the
repository; the manifest retains their retrieval URLs and hashes.
