# Raman, mineralogy and organic evidence layers

`build_evidence.py` creates `dist/data/spectroscopy.json`. It adds locations and
source-linked literature interpretations; it does not classify spectra or derive
organics from the LIBS oxide tables.

## Coverage

The delivered snapshot contains 166 SuperCam Raman acquisition groups (1,285
science product records, sols 57–1854) from the NASA PDS observation masterlist. All
groups have an exact site/drive match to PDS PLACES rover positions. The 251
onboard calibration product records are excluded using case-insensitive target name,
target database name and target type checks. Acquisition records do not imply a
successful mineral detection.

Eighteen curated observations provide a separate evidence layer:

| Category | Count | Meaning |
| --- | ---: | --- |
| Raman mineral detections | 8 | Selected SuperCam detections reported by Lopez-Reyes et al. (2025). |
| Organic detections | 7 | Four Curiosity SAM sample sites and three Perseverance SHERLOC Raman G-band observations. |
| Organic interpretations | 2 | Published SHERLOC PAH interpretations at Quartier and Pilot Mountain. |
| Unresolved luminescence | 1 | Bellegarde fluorescence, with a supported inorganic alternative. |

The curated set is a selection, not a complete inventory. It is not an abundance
survey, absence map, or a geographic polygon of organic-bearing deposits.

## Reproduction

First assemble the existing ChemCam and SuperCam chemistry data. Then run:

```sh
python scripts/spectroscopy/build_evidence.py --input-root /path/to/mars-libs-work
```

The input root may reuse the original `supercam/raw` cache. Missing public PDS
masterlist, localization tables and selected SHERLOC XML labels are downloaded.
Only the Python standard library is required. `verification.json` records source
label hashes, exclusions, counts and the output hash. Re-running changes only
the generation timestamp if the upstream files and curation are unchanged.

## Geographic joins

For SuperCam, site and drive are parsed from each Raman EDR product filename.
They are joined exactly to `best_interp`, falling back to `best_tactical`, then
telemetry. Coordinates retain planetocentric latitude and positive-east
longitude. They locate the rover, not the illuminated spot.

For SHERLOC, the scientific paper establishes the target and observing sol.
The corresponding processed-spectrum PDS XML labels supply SITE and DRIVE
indices, independently checked against the product filename, and joined to
PLACES. This matters at Bright Angel: Cheyava Falls uses site 55/drive 0, while
Apollo Temple uses site 56/drive 0. They are not assigned the same coordinate
merely because they occur on the same block. XML labels do not contain the
informal science target name; that association is explicitly attributed to the
paper.

For SAM, named ChemCam drill-hole or sampling-patch observations supply the
rover workspace proxy. The proxy target, chemistry point ID, observation sol,
and NASA waypoint source remain in each record. The SAM sample-collection or
experiment sol is separate. These positions are not claimed as drill-hole
coordinates. Curiosity does not carry a Raman spectrometer.

No marker footprint is assigned. `footprint: null` is intentional: a millimetre
scan cannot be turned into a kilometre-scale deposit boundary. The underlying
chemistry observations and curated evidence need not be co-spatial within a
rock merely because their rover positions coincide.

## Interpretation hierarchy

`published_organic_detection` follows the cited instrument result. It says
nothing by itself about biological origin. SAM measures products released by
heating or derivatization, rather than an unaltered molecular inventory of the
rock. The Bright Angel SHERLOC records use published Raman G-band evidence,
separately from broad ultraviolet luminescence.

`published_organic_interpretation` retains the PAH interpretation of
Fornaro et al. (2025). It should be displayed as a literature interpretation,
not an independently confirmed chemical identity produced by this app.

`inorganic_alternative_supported` marks Bellegarde's early fluorescence.
Scheller et al. (2024) support inorganic explanations for specific other UV
bands, and Haney et al. (2026) demonstrate an anhydrite:Ce3+ explanation for
the 304/325 nm doublet. The latter interpretation is also attached to Quartier.
It does not automatically negate independent Raman features. Fluorescence
intensity is not converted to organic concentration.

## Primary literature

- Lopez-Reyes et al. (2025), SuperCam Raman observations:
  https://doi.org/10.1029/2025JE008943
- Sharma et al. (2023), early SHERLOC fluorescence associations:
  https://doi.org/10.1038/s41586-023-06143-z
- Scheller et al. (2024), inorganic luminescence alternatives:
  https://doi.org/10.1126/sciadv.adm8241
- Haney et al. (2026), anhydrite:Ce3+ doublet interpretation:
  https://doi.org/10.1029/2025JE009385
- Fornaro et al. (2025), sulfate-associated PAH interpretation:
  https://doi.org/10.1038/s41550-025-02638-z
- Hurowitz et al. (2025), Bright Angel organic/mineral observations:
  https://doi.org/10.1038/s41586-025-09413-0
- Eigenbrode et al. (2018), SAM organic matter at Pahrump Hills:
  https://doi.org/10.1126/science.aas9185
- Freissinet et al. (2025), Cumberland long-chain alkanes:
  https://doi.org/10.1073/pnas.2420580122
- Williams et al. (2026), Mary Anning 3 SAM TMAH experiment:
  https://doi.org/10.1038/s41467-026-70656-0

PDS data and all source links are included in the JSON. Original paper text,
figures and spectra are not redistributed by this layer.
