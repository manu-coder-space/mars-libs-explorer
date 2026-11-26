# Data sources and interpretation

Snapshot retrieval began on 16 November 2026 UTC. The archive coverage is the
coverage of published chemistry products, not the rovers' current operational
sol. The bundled per-mission JSON metadata give the exact counts and dates.

## Curiosity / ChemCam

- [Official PDS overview and release information](https://pds-geosciences.wustl.edu/missions/msl/chemcam.htm)
- [Major-oxide composition (MOC) tables and labels](https://pds-geosciences.wustl.edu/msl/msl-m-chemcam-libs-4_5-rdr-v1/mslccm_1xxx/data/moc/)
- [Observation log](https://pds-geosciences.wustl.edu/msl/msl-m-chemcam-libs-4_5-rdr-v1/mslccm_1xxx/document/msl_ccam_obs.csv)
- [Archive software interface specification](https://pds-geosciences.wustl.edu/msl/msl-m-chemcam-libs-4_5-rdr-v1/mslccm_1xxx/document/chemcam_archsis.pdf)
- [RMI mosaics and annotation labels](https://pds-geosciences.wustl.edu/msl/msl-m-chemcam-libs-4_5-rdr-v1/mslccm_1xxx/extras/rmi_mosaics/)
- [NASA/JPL MMGIS rover waypoints](https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json)

The bundled chemistry contains nine oxides: SiO2, TiO2, Al2O3, FeOT, MgO, CaO,
Na2O, K2O and MnO. Each point retains its published RMSEP and shot standard
deviation. The observation log supplies target metadata and site/drive indices.
Only exact site-and-drive matches are assigned rover coordinates. The MMGIS
GeoJSON itself does not specify the latitude convention; values are retained
as published and must not be silently treated as precision target geodesy.

ChemCam point numbers are official RMI annotation numbers for curated mosaics.
Other points receive chronological order within sequence and target, explicitly
identified by `point_index_kind`; those order numbers are not guaranteed to be
the instrument team's raster numbering.

ChemCam RMI image credit: NASA/JPL-Caltech/LANL/CNES/IRAP. Each source label and
image URL is retained with the corresponding featured target.

## Perseverance / SuperCam

- [Official PDS overview and release information](https://pds-geosciences.wustl.edu/missions/mars2020/supercam.htm)
- [Major-oxide composition CSV](https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/data_derived_spectra/supercam_libs_moc.csv)
- [MOC PDS4 label](https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/data_derived_spectra/supercam_libs_moc.xml)
- [Observation master list](https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/data_observation_log/m2020_scam_masterlist.csv)
- [SuperCam PDS User Guide](https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/document/SuperCam_PDS_Userguide.pdf)
- [Annotated RMI mosaics](https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/data_special_rmi/)
- [Rover PLACES bundle documentation](https://pds-geosciences.wustl.edu/missions/mars2020/places.htm)
- [PLACES best-interpolated localization table](https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_rover_places/data_localizations/best_interp.csv)

The eight common oxides are retained. Published shot standard deviations and
the archive's per-oxide calibration RMSEP are kept separate. The MOC identifiers
are matched to LIBS records in the master list; the few early filename variants
use a constrained join on sol, sequence, spacecraft clock and raster point.
PLACES provides published rover positions, including explicitly named
planetocentric latitude and east longitude. The precise join rules and any
quality flags are recorded in the ingest output. These positions remain rover
proxies, even though the source localization table is called `best_interp`.

SuperCam featured image spots are digitized from the team's own annotated
mosaics; no unmeasured chemical values are filled in. Display JPEGs, where used,
keep the original pixel dimensions. Original PNG URLs remain available.

## Orbital geography and published geology

The basemaps are real orbital images, rendered as bounded raster displays on a
local Mars geographic canvas. They are not Earth Web Mercator maps. Image
metadata use positive-east longitude and the documented Mars geographic frame;
the rebuild uses the Mars sphere radius of 3,396,190 m where a spherical
projection is needed. The source ChemCam waypoint latitude convention remains
unspecified, as described above. Display alignment is not proof of exact
co-registration between the image, geological boundary, rover and laser spot.

| Region/layer | Primary source | Interpretation and display limits |
|---|---|---|
| Gale color HiRISE context | Parker and Calef III, merged orthophoto mosaic; [USGS product page](https://astrogeology.usgs.gov/search/map/mars_msl_gale_merged_orthophoto_mosaic_25cm) | Enhanced source LRGB composite, not calibrated natural color; reduced display sampling is about 4.39 m/pixel, while the source image is 0.25 m/pixel. |
| Regional CTX context | NASA/JPL/MSSS, Caltech Murray Lab and Esri; distributed through [NASA Mars Trek](https://trek.nasa.gov/mars/) | Grayscale uncontrolled mosaic; offsets and seams can remain. |
| Jezero HiRISE/CTX terrain | Fergason et al. (2020), [HiRISE](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_orthorectified_image_mosaic) and [CTX](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_context_camera_orthorectified_image_mosaic) terrain-relative navigation image products, distributed through NASA Mars Trek | Grayscale imagery sampled for display at about 5.09 m/pixel in latitude; source HiRISE resolution is 0.25 m and CTX resolution is 6 m. Transparent HiRISE gaps retain the underlying CTX. |
| Jezero geological units | Sun and Stack (2020), [USGS SIM 3464](https://doi.org/10.3133/sim3464) | Regional 1:75,000 prelanding orbital map. Published units are hypotheses at that map scale, not automatic in-situ mineral identifications. The bundled web-GIS geometry is clipped and simplified for viewing. |
| Gale, Glen Torridon geology | Fedo et al. (2022), [source data](https://doi.org/10.5281/zenodo.7041712), [paper](https://doi.org/10.1029/2022JE007408) | Published annotated raster covering a local study area, not the full Gale traverse. Source bounds have four decimal places, so fine-scale georeferencing precision is limited. |
| Zhurong regional geology, when using the bundled context products | Wu et al. (2024), [source GIS](https://doi.org/10.5281/zenodo.13341513), [paper](https://doi.org/10.1038/s41598-024-75507-w) | Authors' regional geological interpretations; the GIS release predates paper revisions and retains its original unit names. The local excerpt falls inside one regional unit and does not locate the individual LIBS/SWIR targets. |

Exact layer extents, image dimensions, source URLs, hashes, processing and
attribution are recorded in `dist/data/geography.json` and
[scripts/geography/README.md](scripts/geography/README.md). The Gale geological
raster and the Jezero regional unit layer differ in scale, coverage and method;
no unsurveyed area is filled by extrapolating those maps. Unit names selected
at a rover proxy describe the published map at that position, not necessarily
the target several metres away. The white route drawn by the app joins sampled
rover positions and is not the complete navigation traverse.

## Raman acquisition catalogue and curated evidence

`dist/data/spectroscopy.json` has two independent collections. The first is an
acquisition catalogue derived from the SuperCam masterlist: 1,285 science
product records in 166 observing groups, spanning sols 57–1854. Its 251 onboard
calibration records are excluded using case-insensitive target name, database
name and target-type checks. All 166 groups have exact site/drive joins to
PLACES. A FITS product can contain several individual or coadded spectra;
these counts enumerate products, not laser shots or individual spectra.

The second collection contains 18 selected published findings. It is not an
exhaustive mineral or organic survey:

| Evidence class | Included examples | Status carried by the data |
|---|---|---|
| SuperCam Raman minerals | Garde, Bellegarde, Reids Gap, Solva, Ouzel Falls, Lake Haiyaha, Amherst Point, Bills Bay | 8 published mineral detections; separate from acquisition-only records |
| Curiosity SAM organics | Cumberland, Confidence Hills, Mojave 2, Mary Anning 3 | 4 sample sites with published organic products; method and sample/experiment sol retained |
| SHERLOC Raman organic carbon | Walhalla Glades, Cheyava Falls, Apollo Temple | 3 published Raman G-band detections |
| SHERLOC PAH interpretations | Quartier, Pilot Mountain | 2 published organic interpretations from comparison with laboratory analogues |
| SHERLOC unresolved luminescence | Bellegarde | Measured fluorescence with a supported inorganic alternative |

Curiosity has no Raman instrument; its organic evidence here comes from SAM.
SAM detects products released by heating or chemical derivatization. Those
products need not represent the intact original molecules in a rock. The
Perseverance evidence distinguishes a reported Raman G band from broad UV
luminescence. [Scheller et al. (2024)](https://doi.org/10.1126/sciadv.adm8241)
support inorganic explanations for specified UV bands, while
[Haney et al. (2026)](https://doi.org/10.1029/2025JE009385) demonstrate an
anhydrite:Ce3+ explanation for the 304/325 nm doublet. These findings are
attached to the relevant interpretation; they do not automatically negate
independent Raman features.

The app retains the PAH interpretation of
[Fornaro et al. (2025)](https://doi.org/10.1038/s41550-025-02638-z) as a
literature interpretation. The organic-carbon findings in Bright Angel follow
[Hurowitz et al. (2025)](https://doi.org/10.1038/s41586-025-09413-0). None of
these statuses establishes biological origin or generates an organic abundance
surface. A blank area of the map is not evidence of absence.

### Evidence positioning

SuperCam Raman EDR filenames supply site/drive identifiers. SHERLOC target names
and observing sols come from the cited papers; corresponding
[processed-spectrum PDS XML labels](https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_sherloc/data_processed/)
provide SITE and DRIVE indices. The labels are checked against their filenames
and joined to PLACES. Cheyava Falls is site 55/drive 0 and Apollo Temple is site
56/drive 0; they have distinct rover coordinates despite occurring on the same
rock block. The informal science target name is not assumed to be present in
every PDS label.

For Curiosity SAM, named ChemCam drill-hole or sampling-patch observations supply
workspace proxies. Each record retains that proxy's target, point ID,
observation sol and NASA waypoint source. The SAM sample-collection/experiment
sol remains separate. No record claims the rover coordinate is the exact
drill-hole coordinate. No scan footprint is enlarged into a deposit polygon.

Reproduction and validation:
[scripts/spectroscopy/README.md](scripts/spectroscopy/README.md),
`scripts/spectroscopy/build_evidence.py` and
`scripts/spectroscopy/verification.json`. Sources, labels, hashes, row IDs,
position joins and interpretation statuses are retained in the JSON.

### Primary spectroscopy references

- Lopez-Reyes et al. (2025), *SuperCam Raman Activities at Jezero Crater, Mars:
  Observational Strategies, Data Processing, and Mineral Detections During the
  First 1000 Sols*. [doi:10.1029/2025JE008943](https://doi.org/10.1029/2025JE008943)
- Sharma et al. (2023), *Diverse organic-mineral associations in Jezero crater,
  Mars*. [doi:10.1038/s41586-023-06143-z](https://doi.org/10.1038/s41586-023-06143-z)
- Eigenbrode et al. (2018), *Organic matter preserved in 3-billion-year-old
  mudstones at Gale crater, Mars*.
  [doi:10.1126/science.aas9185](https://doi.org/10.1126/science.aas9185)
  · [NASA manuscript](https://ntrs.nasa.gov/api/citations/20200001471/downloads/20200001471.pdf)
- Freissinet et al. (2025), *Long-chain alkanes preserved in a Martian mudstone*.
  [doi:10.1073/pnas.2420580122](https://doi.org/10.1073/pnas.2420580122)
- Williams et al. (2026), *Diverse organic molecules on Mars revealed by the first
  SAM TMAH experiment*.
  [doi:10.1038/s41467-026-70656-0](https://doi.org/10.1038/s41467-026-70656-0)
  · [Open article](https://pmc.ncbi.nlm.nih.gov/articles/PMC13100061/)

## Zhurong / MarSCoDe

The site imports genuine public author-deposited supplements. It does not
include a calibrated Chinese major-oxide table or a geolocated Zhurong LIBS
traverse. The source products have different meanings from the NASA MOC data.

| Source | Files/data included | Published quantity |
|---|---|---|
| [Luo et al., Zenodo 8402478](https://doi.org/10.5281/zenodo.8402478) | Data Set S1: 31 rows; S2: 14 rows; S3: 8 nonempty rows | Li, Sr, S and associated normalized major-element peak areas |
| [Zhang et al., Zenodo 11480713](https://doi.org/10.5281/zenodo.11480713) | Supplemental data 1: 29 rows; data 2: 8 rows | H/S/Cl peak fits, fit quality, widths and normalized peak areas; major-element normalized areas |
| [Zhang et al., Zenodo 16809501](https://doi.org/10.5281/zenodo.16809501) | 30 SWIR spectra at 309 wavelengths each | Source-calibrated reflectance, 850–2390 nm at 5 nm intervals |

The five LIBS tables contain 90 rows collectively; overlapping targets and
different naming conventions mean this is not a count of 90 independent
analyses. The three Luo tables contain 32 distinct published target labels.
No cross-publication target merge is made without a published identifier
crosswalk. Dash cells become null, not zero; empty formatted spreadsheet rows
are omitted.

Normalized peak areas are not wt%, ppm, mineral abundance or Raman intensity.
They depend on spectral line, channel and processing. The source normalization
is retained, including O 777 nm normalization for the S 564 nm measurement.
The Mg 518.51 label is preserved from the spreadsheet even though its Zenodo
description says 518.15 nm. The H/S/Cl spreadsheet does not specify units in its
raw-area/FWHM headers, so those fields remain in source units. Hydrogen, sulfur
and chlorine emission alone does not demonstrate organic molecules.

The SWIR source describes calibration against a white target, despiking and
wavelet filtering. The app preserves the supplied reflectance without new
spectral fitting or mineral assignments. MarSCoDe combines LIBS, SWIR and
microimaging; SWIR reflectance is not a Chinese Mars Raman dataset.

No exact target latitude/longitude is supplied by these supplements. Imported
measurements therefore retain `location: null`. Published rounded landing
coordinates are context only; neither a regional geological map nor the landing
point is substituted for missing target coordinates.

### Access and reproduction

The primary [CNSA Lunar and Planetary Data Release System](https://clpds.bao.ac.cn/web/enmanager/mars1)
requires registration for the relevant Level 2B/associated Tianwen-1 products,
as stated by Luo et al. A publisher Table S2 containing target metadata and
concentrations returned HTTP 403 during this build; it is linked as a source
but not imported. Public author supplements were used without accessing an
account-restricted archive.

All six original downloaded files, plus the CSV extracted from SWIR.zip, are
bundled under `dist/data/zhurong_sources/`. The original files retain published
MD5 values and computed SHA-256 hashes in
`scripts/zhurong/source_manifest.json`. The importer reads OOXML directly and
does not modify the spreadsheets. See
[scripts/zhurong/README.md](scripts/zhurong/README.md) and run
`python scripts/zhurong/ingest_zhurong.py` to reproduce `dist/data/zhurong.json`.
The Python standard library is sufficient for this importer.

### Primary Chinese mission references

- Luo et al. (2024), *Alkali trace elements observed by MarSCoDe LIBS at Zhurong
  landing site on Mars: quantitative analysis and its geological implications*.
  [doi:10.1029/2024JE008366](https://doi.org/10.1029/2024JE008366)
- Zhang et al. (2024), *Volatile elements characterized by MarSCoDe in materials
  at Zhurong landing site*.
  [doi:10.3847/1538-3881/ad6560](https://doi.org/10.3847/1538-3881/ad6560)
- Zhang et al. (2025), *In situ observation of weathering rinds at the Zhurong
  landing site, Mars*.
  [doi:10.1029/2025JE009196](https://doi.org/10.1029/2025JE009196)
- Liu et al. (2026), *Primary evaporite in southern Utopia Planitia on Mars from
  Zhurong rover observations*.
  [doi:10.1038/s41550-026-02917-3](https://doi.org/10.1038/s41550-026-02917-3)

## Derived cation ratios and interpretation

For nonnegative, finite oxide estimates in wt%, the app calculates cation
moles per nominal 100 g using the following conversion factors:

| Oxide | Cation moles |
|---|---|
| SiO2 | wt% / 60.0843 |
| Al2O3 | 2 × wt% / 101.9613 |
| FeOT | wt% / 71.844 |
| MgO | wt% / 40.3044 |
| CaO | wt% / 56.0774 |
| Na2O | 2 × wt% / 61.9789 |
| K2O | 2 × wt% / 94.1960 |

The ternary axes are `Si + Al`, `Ca + Na + K`, and `Fe + Mg`, divided by their
sum for plotting. Ti and Mn are not included in this projection. The original
oxide estimates and totals are not renormalized. Ideal stoichiometric reference
points are feldspar (0.8, 0.2, 0), low-Ca pyroxene (0.5, 0, 0.5), diopside
(0.5, 0.25, 0.25), olivine (1/3, 0, 2/3) and silica (1, 0, 0).

Bulk ratios include `100 Mg/(Mg + total Fe)`, `(Ca + Fe + Mg)/Si`, `Al/Si`,
and `(Fe + Mg)/Si`. A ratio requires finite, nonnegative inputs and a positive
denominator. Negative published predictions remain in the underlying chemistry
tables but are excluded from these derived ratios. The Mg ratio uses total Fe
and does not determine Fe2+/Fe3+. No confidence interval is generated because
the joint oxide covariance is unavailable.

Reference stoichiometry does not uniquely identify a mineral, estimate modal
abundance, hydration or organic content. Mixed grains, non-silicate salts,
glass, dust and calibration uncertainty can produce the same projection.
Common Ca–Mg–Fe pyroxenes have `(Ca + Fe + Mg)/Si` near 1 and olivine near 2;
Na–Al pyroxenes are outside that simple comparison. Compare the source studies
for examples that combine chemistry with other instruments:
[Clavé et al.](https://doi.org/10.1029/2022JE007463) and
[Beyssac et al. (2023)](https://doi.org/10.1029/2022JE007638).

## Source rights and attribution

Original application code is MIT licensed. The MIT license does not relicense
scientific data, images, maps or papers from other authors.

- The Luo and Zhang Zenodo records listed above declare **CC BY 4.0**. Credit
  their authors and data DOIs, retain the license link
  <https://creativecommons.org/licenses/by/4.0/>, and identify the app's table
  extraction, null handling and display as processing of those sources.
- The Fedo et al. Glen Torridon data and Wu et al. Zhurong regional GIS are
  **CC BY 4.0**. Retain author/DOI attribution and identify cropping,
  resampling, reprojection or simplification when applicable. Regional map
  interpretations remain the authors' interpretations.
- Gale's USGS HiRISE product reports no use constraints. Retain Parker and
  Calef III and mission/instrument credits. Jezero context retains Fergason
  et al. and NASA/JPL/USGS/HiRISE/CTX credits from its source metadata.
- CTX context retains NASA/JPL/MSSS, Caltech Murray Lab and Esri attribution.
  The Sun and Stack web-GIS service is used as a viewing layer; the displayed
  clipping/simplification is not a new analytical geologic mapping product.
- NASA PDS/RMI and SHERLOC product credits remain with their sources.
  Literature findings are paraphrased and linked; paper figures, full text
  and proprietary spectral libraries are not redistributed by the evidence
  catalogue.

The per-layer metadata and importer READMEs provide the exact source-specific
attributions and transformations for the bundled assets.

## Primary calibration and spatial references

1. Clegg et al. (2017), *Recalibration of the Mars Science Laboratory ChemCam
   instrument with an expanded geochemical database*. Spectrochimica Acta Part B.
   [doi:10.1016/j.sab.2016.12.003](https://doi.org/10.1016/j.sab.2016.12.003)
2. Anderson et al. (2022), *Post-landing major element quantification using
   SuperCam laser induced breakdown spectroscopy*. Spectrochimica Acta Part B.
   [doi:10.1016/j.sab.2021.106347](https://doi.org/10.1016/j.sab.2021.106347)
   · [NASA accepted manuscript](https://ntrs.nasa.gov/api/citations/20220000028/downloads/SuperCam_Calibration_Paper_accepted.pdf)
3. Goetz et al. (2023), *Determination of Spatial Scale in Martian Landscape
   Images Acquired by the Curiosity Rover, and Viewing Image Scale and Target
   Chemistry Using the ASIC Website*. Earth and Space Science.
   [doi:10.1029/2020EA001611](https://doi.org/10.1029/2020EA001611)
4. Frydenvang et al. (2020), *The chemostratigraphy of the Murray formation and
   role of diagenesis at Vera Rubin Ridge in Gale crater, Mars, as observed by
   the ChemCam instrument*. Journal of Geophysical Research: Planets.
   [doi:10.1029/2019JE006320](https://doi.org/10.1029/2019JE006320)

Use the data-product versions and source hashes in a methods statement, not
only this explorer's title. This explorer has not recalibrated the spectra and
does not estimate mineral modes from major oxides alone. Cross-mission visual
comparisons preserve each mission's original calibration and require a
separate uncertainty and sampling assessment for quantitative interpretation.
