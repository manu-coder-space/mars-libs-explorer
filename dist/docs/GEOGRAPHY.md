# Mars imagery and published geology

`dist/data/geography.json` describes independently sourced geographic context.
It does not derive terrain, mineralogy, or organics from the LIBS points. The
frontend draws the `basemaps` in listed order, followed by any enabled geology.
All image bounds are `[west, south, east, north]`, in degrees on Mars.

## Sources and meaning

| Layer | Source and attribution | Display preparation and limits |
|---|---|---|
| Regional CTX terrain | NASA/JPL/MSSS/Caltech Murray Lab/Esri; the `CTX_beta01_uncontrolled_5m_Caltech` product catalogued by [NASA Mars Trek](https://trek.nasa.gov/tiles/Mars/EQ/CTX_beta01_uncontrolled_5m_Caltech/1.0.0/WMTSCapabilities.xml) | Bundled grayscale tile mosaics. This beta01 mosaic is uncontrolled; seams and local position offsets may occur. No color is synthesized. |
| Gale HiRISE LRGB | Timothy Parker and Fred J. Calef III, NASA/JPL-Caltech/USGS/UArizona, [July 2025 color mosaic](https://astrogeology.usgs.gov/search/map/mars_msl_gale_merged_orthophoto_mosaic_25cm) | Native 0.25 m RGB strips fused by the source authors to the mission RED orthomosaic. Reduced to 2048 × 4324 pixels (about 4.39 m/pixel). Source grayscale strips and all seams retained. Enhanced display colors are not chemical abundances or calibrated natural-color measurements. |
| Jezero CTX and HiRISE | USGS Mars 2020 Terrain Relative Navigation products, Fergason et al. (2020), NASA/JPL/MSSS and NASA/JPL/UArizona; [HiRISE record](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_orthorectified_image_mosaic), [CTX record](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_context_camera_orthorectified_image_mosaic) | Published grayscale orthomosaics served by NASA Mars Trek. Both are sampled at about 5.09 m per pixel in latitude; CTX's source resolution is 6 m and HiRISE's is 0.25 m. HiRISE data gaps remain transparent over CTX. |
| Jezero geologic units | Sun, V.Z. and Stack, K.M. (2020), USGS SIM3464, [doi:10.3133/sim3464](https://doi.org/10.3133/sim3464) | Real published unit polygons, clipped to the displayed region and simplified by about 2 m. Map scale 1:75,000; prelanding orbital interpretations do not constitute a current mineral classifier. The USGS web service is for viewing purposes; use the linked official PDF/GIS for scientific analysis. |
| Glen Torridon geologic map | Fedo et al. (2022), [doi:10.5281/zenodo.7041712](https://doi.org/10.5281/zenodo.7041712); associated paper [doi:10.1029/2022JE007408](https://doi.org/10.1029/2022JE007408), CC BY 4.0 | Original annotated JPEG map panel, positioned using the authors' corner coordinates. Bounds are published to four decimal places, so placement is only several metres precise. Coverage is local (~0.9 × 1.0 km), not the full Gale traverse. Original yellow route, white sample circles, contour labels, contacts and cross-section line remain part of the source map. No machine-readable polygons or unit classifications are invented. |
| Southern Utopia regional geology | Wu et al. (2024), [doi:10.5281/zenodo.13341513](https://doi.org/10.5281/zenodo.13341513), paper [doi:10.1038/s41598-024-75507-w](https://doi.org/10.1038/s41598-024-75507-w), CC BY 4.0 | Author-released regional unit shapefiles and landing point. Marine terminology represents the authors' interpretation; it is not a confirmed ancient-ocean detection. The archive's original unit names are preserved, including differences from the final paper's revised age terminology. Landing position is context, not a LIBS target coordinate. |

The USGS Gale image record lists no use constraints and requests author credit.
USGS's Jezero map page identifies the map as public domain. The source credits
and CC BY licenses above remain attached to derived display assets.

## Coordinates and alignment

The adopted reference sphere is Mars 2000, radius **3,396,190 m**. The basemaps
use a geographic equirectangular grid, not Earth's Web Mercator. The official
WMTS metadata and Esri tile metadata agree on a top-left corner of (-180°,90°),
two tiles horizontally and one vertically at zoom zero, and a tile angular
width of `180 / 2**zoom` degrees. Regional CTX tiles are 512 pixels wide; Jezero
TRN tiles are 256 pixels wide. Exact image extents are derived from this grid.

The Gale COG has an explicit equirectangular transform, central meridian and
standard parallel both zero, and the same Mars radius. Its full pixel footprint
is converted analytically into longitude/latitude bounds. No guessed control
points or invented color were used. The Jezero GIS service is requested in
`ESRI:104971`, the Mars 2000 sphere geographic coordinate system. Author
Zhurong shapefiles are transformed from Mars equirectangular to geographic
coordinates on the same sphere.

GeoJSON files explicitly declare Mars coordinate semantics. Their numeric
coordinates must **not** be treated as WGS84 positions. ChemCam's downloaded
rover localization values are preserved; their original feed does not explicitly
declare the latitude convention, so this project does not independently certify
that convention. Both mission chemistry locations remain rover proxies, not
the actual laser spots.

A direct alignment check overlays 9,205 Curiosity measurements that fall in the
Glen Torridon panel. They closely follow the published route and sample sites
across the panel. This supports the geographic placement at the stated precision;
it does not establish sub-metre registration or validate geological interpretations.

## Rebuild

The application uses bundled files and needs no geospatial packages at runtime.
To reproduce the display assets, install the Python requirements and system
GDAL (`ogr2ogr`), then run from the repository root:

```sh
python scripts/geography/build_geography.py --cache /absolute/path/to/geography-cache
```

The cache can be outside the checkout; it contains public source downloads and
tiles, including the ~74 MB Zhurong author GIS archive. The Gale source is a
~1 GB cloud-optimized TIFF, but only its reduced overview is read through HTTP
range requests. Keep raw caches out of Git. Source tile URLs, hashes, extents,
image hashes, source-feature counts and processing notes are recorded with the
output metadata and source manifest. Missing or corrupt image downloads cause
a rebuild failure; the pipeline does not fabricate a replacement tile.

The published Gale raster already contains text and a route. Its legend is
described in metadata rather than extracted through an image classifier. Unit
swatches for that raster and the Zhurong regional map are display colors; the
Jezero polygon colors are taken from the published USGS service renderer.
