# Mar-to-gis

Mar-to-gis is a geological workspace for comparing published Mars maps with rover chemistry and spectroscopy. It shares the validated data archive of Mars LIBS Explorer and adds a map-centred interface, published Jezero contacts and landforms, spatial selection, descriptive chemistry tools, and portable interpretation workspaces.

**GitHub Pages route:** <https://manu-coder-space.github.io/mars-libs-explorer/Mar-to-gis/>

The application is in `dist/Mar-to-gis/`. Its relative route is `Mar-to-gis/` beneath the existing site. The parent Mars LIBS Explorer remains accessible through the interface. Keep the parent `dist/data/` directory with the application: the new folder deliberately shares those data instead of duplicating them.

## Regional coverage

| Region | Published map context | Rover data and spatial limits |
| --- | --- | --- |
| Jezero / Perseverance | Sun & Stack (2020), USGS SIM 3464, scale 1:75,000; CTX and HiRISE grayscale imagery; geological polygons, contacts and mapped landforms | SuperCam LIBS analyses and rover-position proxies; separate published spectroscopy evidence and Raman acquisition locations |
| Gale / Curiosity | Enhanced-colour HiRISE imagery and Fedo et al. (2022) local Glen Torridon raster stratigraphy | ChemCam LIBS analyses and rover-position proxies; published SAM organic evidence; the local geological raster cannot provide automatic polygon-based unit assignments |
| Southern Utopia / Zhurong | Wu et al. (2024) regional geomorphic map, retaining the accompanying August 2024 GIS archive's original unit labels | Landing context and links to published MarSCoDe LIBS/SWIR supplements; no verified target coordinates are available for those supplementary spectra |

The Jezero **polygon layer is a clipped display excerpt**: 229 polygons representing 11 units, covering 77.10–77.59° E and 18.30–18.64° N. The original source service contains 1,308 unit polygons. The workspace's **Map extent** command uses the clipped polygon footprint.

The added Jezero **line layer covers the larger published regional map**, approximately 76.8–77.8° E and 17.7–18.7° N. Consequently, published traces can remain visible outside the bundled polygon footprint. A point outside that footprint receives no polygon-based unit assignment even if linework is present nearby. This difference in coverage is not evidence that mapped geology is absent.

Glen Torridon's raster is a local map, approximately 0.9 by 1.0 km; it does not classify all of Gale crater. Zhurong's regional map contains interpretations of landform origin. Its marine terminology reflects the authors' interpretation and is not independent confirmation of an ancient ocean. Original archive unit terminology can differ from the revised final paper.

## Working in the map

1. Choose **Jezero**, **Gale**, or **Utopia**. Select an orbital basemap and adjust geological opacity. Published geology colours and measurement colours are separate layers.
2. Turn the rover traverse, chemistry, contacts, landforms and spectroscopy layers on or off. In Jezero, select a mapped feature type to isolate lineaments, ridges, channels, crater rims or delta fronts.
3. Use **Inspect** to read a map unit, published trace or rover position. Select an individual observation to see its oxide values, source row, original source link, quality flags, separate RMSEP and shot-standard-deviation values, and available position provenance. For Jezero observations, the inspector reports approximate distance from the rover proxy to the nearest published contact.
4. Filter by target/observation ID, sol interval, archive quality flags or published unit beneath the rover. **Select area** draws a rectangle that restricts the linked observations. Panning and zooming alone change the view, not the selected LIBS records.
5. Use **Measure** for approximate distances on a Mars sphere. **Rover extent**, **Map extent**, zoom buttons and keyboard navigation help reposition the map.
6. Record your interpretation in **Notes & provenance**. **Save workspace** downloads `Mar-to-gis-workspace.json`; **Restore workspace** reapplies its region, view, filters, area selection, notes and imported layers.

The workspace is a browser application. Imported layers and notes stay in browser storage unless you download them. Keep a downloaded workspace as a portable backup; browser storage has capacity and persistence limits. A restored workspace records its earlier archive snapshot and warns when filters are being applied to a different current data snapshot.

## Interpretation tools

**Compare units** provides counts, distinct rover positions, median and 25th–75th percentile interval for the selected metric, grouped by the published polygon under each rover proxy. The interval describes the data distribution; it is not a confidence interval. Repeated shots, repeated targets and multiple records from one position are not independent geological samples.

**Chemical relationships** contains an oxide scatter plot and a cation ternary plot with vertices Si + Al, Ca + Na + K, and total Fe + Mg. The selectable derived descriptors include Mg/(Mg + total Fe), Ca/Al, (Na + K)/Al and total Fe/Mg. Cations are calculated from the archived oxide estimates and molar masses. Only the ternary proportions are normalized for plotting. These descriptors do not uniquely determine minerals or mineral fractions.

**Mapped orientations** displays a length-weighted axial rose for Jezero's published landform traces within the selected area, or within the current map view if no area is selected. Contacts are excluded. Axial azimuth is clockwise from north over 0–180°; opposite petals repeat the same axial bin. Petal area is proportional to total segment length. Examine one source class at a time for a geological interpretation. This describes the digitized surface traces and does not infer fault sense, subsurface geometry or tectonic stress.

## Published Jezero line data

The bundled file contains **2,878 drawable source features**. The application omits the artificial map frame, leaving **2,877 displayed features: 2,495 contacts and 382 landform traces** before filtering by view or category.

| Source classification | Displayed features |
| --- | ---: |
| Certain contact | 1,666 |
| Approximate contact | 829 |
| Fluvial channel | 6 |
| Crater-rim crest | 66 |
| Buried-crater crest | 4 |
| Ridge crest | 176 |
| Lineament | 98 |
| Delta-lobe front | 32 |

Original classifications and attributes are retained. Certain contacts are solid and approximate contacts are dashed. One additional source contact, `OBJECTID 4879`, has no drawable geometry; its omission is recorded in the source manifest. Lineaments and ridges are not automatically tectonic faults.

Contacts use a 2 m Douglas–Peucker display simplification with original vertices retained. Landform traces have no further simplification beyond the service's six-decimal coordinate output. Neither the decimal precision nor the simplification tolerance states positional accuracy. The publication scale remains 1:75,000. The hosted service is a viewing product; use the linked official USGS GIS and map sheets for publication-grade spatial analysis.

## Scientific limits

- A chemistry marker is a **rover-position proxy**, not a surveyed laser footprint. Markers aggregate records at that position; their colour is the median selected metric. A remotely sampled target may lie in a different geological unit from the rover. Polygon overlap and nearest-contact distance therefore provide spatial context, not definitive target lithology.
- The 2020 Jezero map is a pre-landing orbital interpretation. Its unit names and historical interpretations are retained with their date. Published boundaries, raster registration, rover localisation and target offsets have separate uncertainties.
- Archived major-oxide values are not renormalized to 100%. Negative estimates remain visible in the observation table and original-value CSV fields, while numerical summaries, ratios and chemistry plots require finite, nonnegative inputs. Ratio denominators must be positive. FeOₜ represents total iron expressed as FeO; the derived ratios do not determine the iron oxidation state.
- RMSEP describes calibration prediction error and shot SD describes repeat-shot spread. They are exported separately and are not combined into an unsupported joint confidence interval. Archive flags remain available for inspection and filtering.
- A Raman acquisition records where Raman was acquired; it is not itself a mineral identification. Curated mineral detections, organic detections, interpretations and unresolved luminescence are separate evidence categories. Curiosity has no Raman instrument; its organic evidence here comes from SAM. SHERLOC fluorescence is not uniquely organic and does not establish biological origin.
- Zhurong supplementary LIBS peak areas are not calibrated oxide wt%; SWIR reflectance is not Raman. Supplementary tables can overlap between publications. Unverified target positions are not invented or assigned wholesale to the landing location.
- The workspace does not interpolate chemistry across unsampled ground. Its statistical and spatial tools support interpretation while retaining the distinction between observations and geological hypotheses.

## Import, export and planetary coordinates

The map uses **Mars east longitude and latitude**, with a sphere radius of **3,396,190 m** for distance and local projection calculations. The published Jezero map is returned in **Mars_2000_Sphere, ESRI:104971**, with planetocentric latitude. Native source projection details are retained in the manifest. ChemCam's original latitude convention remains unspecified by its source and is preserved rather than silently converted.

**Import Mars vector layer** accepts a GeoJSON-style `FeatureCollection` containing Point, LineString, MultiLineString, Polygon or MultiPolygon features. Prepare Mars longitude/latitude degrees in the appropriate Mars frame and confirm that coordinate convention before importing. The interface validates numeric ranges, but cannot establish a file's true planetary reference frame. It does not reproject Earth coordinates, projected metre coordinates or planetographic latitude. Limits are 8 MB, 20,000 features and 300,000 vertices per imported file. Imported interpretations remain separate from the published polygons used for automatic unit grouping.

Exports are:

- **CSV:** filtered LIBS records, original oxides, separate uncertainties, quality flags, position provenance, unit overlap, selected metric and original source information. Unlocated records remain available unless a spatial filter excludes them.
- **Mars vectors:** filtered located LIBS records and selected evidence; enabled published vector features intersecting the view or selected area; and visible user layers. Intersecting vector features are retained whole, not clipped. The file includes explicit planetary metadata, a Mars CRS WKT string, export time and spatial/provenance notes.
- **Map:** a PNG of the displayed map with source attribution and spatial cautions.
- **Mars CRS (.prj):** the spherical Mars geographic definition, available in Notes & provenance.
- **Workspace JSON:** filters, region, view, selection, notes, archive snapshot reference and user layers; it does not embed the full shared NASA archive.

Planetary vector exports intentionally use GeoJSON-style geometry with extra Mars metadata. They are **not RFC 7946 Earth/WGS84 datasets**. Desktop GIS software may otherwise assume WGS84. Assign the intended Mars geographic CRS explicitly when loading these coordinates; do not transform them from an incorrectly assumed Earth CRS. The supplied `.prj` describes the map frame and does not resolve ChemCam's unspecified source latitude convention. Work near contacts requires additional assessment of localisation, target offsets and map scale.

## Shared data and scheduled updates

The existing repository's scheduled GitHub workflow checks the NASA archive and only publishes data accepted by its validation pipeline. Mar-to-gis reads those shared parent data files, so accepted archive changes become available here without maintaining a second science-data copy. The footer reports the recorded check and accepted-update times; new releases depend on upstream archive availability.

**Published geology and curated evidence remain reviewed snapshots.** A daily archive check does not automatically adopt new geological papers, change unit interpretations, validate organic claims or substitute new Chinese spectroscopy releases. Revised or removed historical measurements and changed curated evidence can be held for review under the existing updater's rules. The new line layer is a pinned source snapshot, rebuilt intentionally with its own manifest and review.

## Run locally and reproduce the line layer

From the repository root, serve the complete `dist/` directory:

```sh
python -m http.server 8000 --directory dist
```

Open <http://localhost:8000/Mar-to-gis/>. A local server is required for the JSON fetches; opening the HTML directly as a local file is insufficient.

The new source builder uses only Python's standard library:

```sh
python scripts/build_gis_layers.py --cache .cache/gis-lines
```

It uses cached source responses where available and downloads any missing response. An intentional refresh can use `--refresh`; inspect the resulting source changes before accepting a revised map snapshot. The builder obtains contact layer 5 and linear-feature layer 6 from the official service, requests Mars geographic coordinates, retains original attributes, records the geometry omission, simplifies display contacts and writes:

- `dist/Mar-to-gis/data/jezero-lines.geojson`
- `dist/Mar-to-gis/data/sources.json`

The manifest includes source queries, raw-response SHA-256 hashes, input/output feature counts, original and displayed coordinate counts, exact output bounds, processing, source projection WKT and the output file hash. The browser verifies the line asset against its manifest. To check the pinned source geometry and the distinct polygon/line coverage:

```sh
python scripts/check_gis_sources.py
```

This check deliberately validates the reviewed snapshot's expected classifications and counts. A legitimate source revision requires review of those expectations as well as the new manifest.

## Original references and data access

- Sun, V. Z., and Stack, K. M. (2020). *Geologic map of Jezero crater and the Nili Planum region, Mars.* USGS Scientific Investigations Map 3464, scale 1:75,000. <https://doi.org/10.3133/sim3464>. Official map/GIS download page: <https://pubs.usgs.gov/sim/3464/>.
- Jezero official hosted viewing map: <https://usgs.maps.arcgis.com/apps/webappviewer/index.html?id=a0ae4b521f7a4a6ca2cf0f0c551d5293>. Its feature service and exact queries are recorded in `sources.json`.
- Fedo et al. (2022), Glen Torridon geology: <https://doi.org/10.1029/2022JE007408>. Associated published map: <https://doi.org/10.5281/zenodo.7041712>.
- Wu et al. (2024), southern Utopia regional mapping: <https://doi.org/10.1038/s41598-024-75507-w>. Associated GIS archive: <https://doi.org/10.5281/zenodo.13341513>.
- NASA PDS ChemCam archive: <https://pds-geosciences.wustl.edu/missions/msl/chemcam.htm>.
- NASA PDS SuperCam archive: <https://pds-geosciences.wustl.edu/missions/mars2020/supercam.htm>.
- Imagery, individual spectroscopy papers and archive provenance are linked in the application's **Sources & methods** panel and shared `dist/data/geography.json`, `dist/data/spectroscopy.json` and mission metadata. Original authorship, mission credits and dataset terms remain with the sources.
