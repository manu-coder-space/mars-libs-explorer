# Zhurong / MarSCoDe: verified public supplements

This importer adds genuine Chinese Mars LIBS peak measurements and SWIR
reflectance spectra. It does not manufacture a major-oxide table, target
coordinates, Raman spectra, organic detections or a continuous spatial field.

## Data included

| Source | Included records | Meaning |
|---|---:|---|
| Luo et al. Zenodo 8402478, Data Set S1 | 31 rows | Li and associated major-element normalized peak areas |
| Luo et al. Zenodo 8402478, Data Set S2 | 14 rows | Sr and associated major-element normalized peak areas |
| Luo et al. Zenodo 8402478, Data Set S3 | 8 nonempty rows | S and associated major-element normalized peak areas |
| Zhang et al. Zenodo 11480713, Supplemental data 1 | 29 rows | H/S/Cl fitted peak areas, fit quality, FWHM and normalized areas |
| Zhang et al. Zenodo 11480713, Supplemental data 2 | 8 rows | Major-element normalized peak areas in sulfur-bearing rocks |
| Zhang et al. Zenodo 16809501, SWIR.zip | 30 spectra | Published calibrated SWIR reflectance, 309 wavelengths from 850 to 2390 nm at 5 nm intervals |

The first three tables cover 32 distinct published target labels. These are
**90 table rows, not 90 independently identified measurements**: tables and
papers overlap. The Zhang volatile and Luo target names have not been merged
without an explicit published crosswalk. Blank formatted rows in S3 are omitted.

All source files above carry CC BY 4.0 in the Zenodo API metadata. The six
original files are bundled under `dist/data/zhurong_sources/`, together with the
unaltered CSV contained in SWIR.zip. Published MD5s, computed SHA-256s, source
URLs and physical spreadsheet row numbers are retained. The importer reads
OOXML directly and does not edit the downloaded spreadsheets.

## Refresh

```bash
python scripts/zhurong/ingest_zhurong.py
```

This uses the bundled source files if present; otherwise it downloads the
specific versioned Zenodo files. Every original file must match the publisher's
recorded MD5. `--input-dir /absolute/path` can supply originals under their
published filenames. The output is `dist/data/zhurong.json` and the source
manifest is regenerated next to this script.

## Quantities and geography

Normalized LIBS peak areas are **not wt%, ppm, mineral abundances or Raman
intensities**. They depend on the instrument, channel, line and normalization.
Luo et al. describe channel normalization for Li/Sr and O 777 nm normalization
for S 564 nm. The source's Mg 518.51 label is retained even though Zenodo's
description says 518.15 nm. Do not silently relabel it.

The H/S/Cl spreadsheet does not give units in its raw-area/FWHM headers, so the
importer labels those fields as source units instead of assuming a unit. Dash
cells become null, never zero. Hydrogen, sulfur and chlorine emission does not
by itself identify organic matter.

The SWIR readme states that spectra were calibrated against the white target,
then despiked and wavelet filtered. The importer retains these reflectances
without reprocessing, spectral matching or invented mineral assignments.

None of these files includes exact target latitude/longitude. Every imported
observation and spectrum therefore has `location: null`. Rounded published
landing coordinates (25.066 N, 109.925 E) are provided separately as context
only. They must not be attached to each spectral measurement.

MarSCoDe comprises LIBS, SWIR and microimaging. The Chinese spectral data here
provide additional mineralogical context; they are not a Chinese Mars Raman
dataset.

## Primary archive access and remaining download

Luo et al. explicitly state that Level 2B and associated Tianwen-1 data are
available through the CNSA Lunar and Planetary Data Release System after
registration: <https://clpds.bao.ac.cn/web/enmanager/mars1>.

Their publisher lists Table S2 (18.8 KB), which contains scientific-target
metadata and concentrations. Its public download returned HTTP 403 in this
build, so that table is not imported. The application exposes its reference
without treating signal ratios as concentrations. No account-restricted data
were accessed.

## References

- Luo et al. (2024), *Alkali trace elements observed by MarSCoDe LIBS at Zhurong
  landing site on Mars: quantitative analysis and its geological implications*.
  <https://doi.org/10.1029/2024JE008366>
- Luo et al. data: <https://doi.org/10.5281/zenodo.8402478>
- Zhang et al. (2024), *Volatile elements characterized by MarSCoDe in materials
  at Zhurong landing site*. <https://doi.org/10.3847/1538-3881/ad6560>
- Zhang et al. volatile data: <https://doi.org/10.5281/zenodo.11480713>
- Zhang et al. (2025), *In situ observation of weathering rinds at the Zhurong
  landing site, Mars*. <https://doi.org/10.1029/2025JE009196>
- Zhang et al. reflectance data: <https://doi.org/10.5281/zenodo.16809501>
- Liu et al. (2026), *Primary evaporite in southern Utopia Planitia on Mars from
  Zhurong rover observations*. <https://doi.org/10.1038/s41550-026-02917-3>

The two app interpretation cards are attributed summaries of those studies,
not new app-generated discoveries. In particular, gypsum/selenite is a
mineralogical interpretation from multiple instruments, not an organic claim.
