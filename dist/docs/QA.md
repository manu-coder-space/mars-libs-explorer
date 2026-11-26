# Verification record

## Data checks

Both mission ingests retain source URLs, file hashes and archive identifiers.
ChemCam verifies all 42 MOC table row counts against their PDS labels, unique
product IDs, observation-log joins and curated RMI associations. SuperCam
verifies every chemistry/SD/total/distance value against its MOC row, all exact
site/drive localization matches, identical duplicate rows and annotation joins.
The per-mission ingest reports are included under `scripts/`.

The website packaging check passes for 43,296 unique analyses: 42,397 science
points and 899 onboard calibration points. It checks chunk hashes, gzip
round-trips, unique identifiers, finite numeric fields, source references,
coordinate bounds, image hashes and RMI-to-chemistry identity. Results are in
`VALIDATION.json`. No chemical interpolation or renormalization is performed.

## Browser checks

The local hosted preview was exercised in Chrome:

- Both mission datasets load from their bundled assets.
- Searching for Mara_1 returns its five ChemCam measurements.
- Selecting image spot 3 displays SiO2 45.60 wt%, RMSEP 5.00 wt%, shot SD
  1.90 wt%, total 89.19 wt%, and the correct source product/row.
- The downloaded CSV contains those five records, all nine ChemCam oxides,
  their separate RMSEP and shot SD columns, and source/geography identifiers.
- The map's SVG download parses successfully and contains 1,177 geographic
  markers for the full default ChemCam selection, with units, color-scale
  bounds, snapshot date and an explicit rover-proxy caption.
- Switching to SuperCam displays 12,121 unique records and archive version 16.0.
- The Tselhchee image's target filter correctly finds the Tselchee name used by
  MOC and returns nine records at sol 15. Annotation 4 remains without chemistry.
- Selecting MgO updates the map, spot overlay and detail units. Tselchee point 1
  displays MgO 1.66 wt%, RMSEP 1.10 wt% and shot SD 0.60 wt%.
- Mouse and keyboard selection of SuperCam spot 8 display MgO 10.90 wt%,
  RMSEP 1.10 wt% and shot SD 2.51 wt%. The unmatched spot 4 displays no values.
- The local RMI oxide selector, color legend and live readout stay synchronized
  with the global chemistry controls.
- Images load at their intended original dimensions, and the desktop page does
  not overflow the viewport horizontally.

JavaScript syntax checks pass. The GitHub workflow has been supplied using
GitHub's documented Pages actions; it has not been run in a user GitHub account.

## Geography and spectroscopy upgrade — 2026-11-16

Source validation and independent reviews passed for the added datasets. See
`CONTEXT_VALIDATION.json`, `scripts/geography/qa_report.json`,
`scripts/spectroscopy/verification.json` and
`scripts/zhurong/verification_report.json` for detailed counts and checks.
The original NASA chemistry bundle was revalidated without changing values.

- Seven real geographic images decode and match their hashes; both NASA rover
  science traverses are inside bundled imagery bounds. Jezero has 229 display
  polygons. Glen Torridon remains a limited, explicitly bounded source raster.
- Raman catalogue: 166 observation groups, 1,285 product records, 251 calibration
  records excluded. All positions were independently joined to original source rows.
- Eighteen literature findings retain categories, methods, identifiers and
  coordinate provenance. No organic abundance field or unsampled polygon is generated.
- Zhurong: all 775 peak cells, 180 missing cells, 9,270 reflectance values and 309
  wavelengths verified against the downloaded originals. Targets remain unlocated.
- Independent numerical checks cover forsterite, fayalite, diopside, albite,
  anorthite, jadeite, concentration-scale invariance, missing/negative values and
  zero denominators. Jadeite also demonstrates why the pyroxene guide is qualified.

Browser verification used the actual static application in Chromium. The full
Gale color traverse, local Glen Torridon map, Jezero colored unit polygons,
evidence selection, legend/ratio separation, and Chinese table/spectrum controls
were exercised. A 390 px iframe provided a 375 CSS-pixel usable viewport;
responsive light and dark layouts had no page-level horizontal overflow. This
checks responsive layout, not physical-device touch behavior.

Selected-value regression: SuperCam Tselchee spot 8 reports MgO 10.90 wt%,
RMSEP 1.10 and shot SD 2.51. Spot 4 remains explicitly unmatched via keyboard.
Reids Gap correctly displays 3 raster points and 6 product records, not 3 spectra.
Cheyava Falls opens its distinct site/drive-derived position and organic G-band
interpretation. The Chinese FWHM selection retains source FWHM units, and
Sol276_target2 renders its calibrated 850–2390 nm SWIR series.

A downloaded Chinese CSV was parsed and checked for scientific column headers,
units, source metadata, and the exact first Li value. A downloaded map SVG was
parsed as XML and contains embedded geographic raster content with source captions.
The geographic SVG is a raster map inside SVG; the scatter export remains vector.
No application console errors were observed; unrelated browser-extension diagnostics
were excluded. The portable source ZIP is integrity-checked and its bounded
transport parts are verified by SHA-256 during browser download.

## GitHub import validation

The portable bundle retains source identifiers, imagery and scientific values.
Its point and traverse hashes, row counts, calibration exclusions, geolocation
joins and Raman evidence invariants pass the same validators as the original
explorer. The browser also checks chemistry chunks against their recorded
SHA-256 when Web Crypto is available, detecting a mixed or incomplete cached
release during a Pages update.

The GitHub package contains no private Site identity, deployment credentials,
Git repository metadata or raw download caches. Public Pages deployment is
controlled by the ENABLE_PAGES repository variable and defaults to disabled.
Actual repository creation and GitHub-hosted workflow execution require the
account connection and have not been claimed by this prepared package.

The standalone GitHub updater was exercised locally on 16 November 2026. All 109 watched sources were unchanged, with zero source errors or review items. Its local check preserved the data-update timestamp and kept the GitHub schedule marked as not yet activated.
