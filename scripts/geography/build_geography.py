#!/usr/bin/env python3
"""Rebuild bundled Mars geography from primary public archives.

This is cartographic display preparation, not a mineral/organic classification.
Dependencies: Pillow, numpy, rasterio, shapely, pyproj; GDAL ogr2ogr for optional
author shapefiles. All coordinates remain on Mars (no Earth datum conversion).
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, io, json, math, pathlib, time, urllib.error, urllib.parse, urllib.request
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
RADIUS = 3396190.0
DEGREE_M = math.pi * RADIUS / 180
GALE_COLOR = "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/Mars/MSL/MSL_Gale_HiRISE-LRGB_78quads_sharp_cog.tif"
GALE_PAGE = "https://astrogeology.usgs.gov/search/map/mars_msl_gale_merged_orthophoto_mosaic_25cm"
GLEN = "https://zenodo.org/api/records/7041712/files/Fedo_et_al_JGR-P_2022_Glen_Torridon_Gale_Mars.jpeg/content"
JEZERO_SERVICE = "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Jezero_FeatureServiceFromPro/FeatureServer"
CTX_GLOBAL = "https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/{z}/{y}/{x}"
JEZERO_CTX = "JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0"
JEZERO_HIRISE = "JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first_dd"

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fetch(url, cache, name=None, missing_ok=False):
    path = cache / (name or hashlib.sha256(url.encode()).hexdigest())
    if path.exists():
        return path.read_bytes()
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mars-LIBS-Explorer/2.0 scientific-cartography"})
            with urllib.request.urlopen(req, timeout=40) as response:
                data = response.read()
            break
        except urllib.error.HTTPError as error:
            if missing_ok and error.code == 404:
                return None
            if error.code not in [429, 500, 502, 503, 504] or attempt == 2:
                raise
            time.sleep(attempt + 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data

def tile_mosaic(template, bounds, zoom, tile_px, cache, filename, missing_ok=False):
    # The official Trek/Esri Mars geographic tile grid has z0=2 x 1 tiles.
    # It is longitude/latitude, not Earth Web Mercator.
    west, south, east, north = bounds
    step = 180.0 / (2 ** zoom)
    x0, x1 = math.floor((west + 180) / step), math.ceil((east + 180) / step)
    y0, y1 = math.floor((90 - north) / step), math.ceil((90 - south) / step)
    out = Image.new("RGBA", ((x1 - x0) * tile_px, (y1 - y0) * tile_px))
    tasks = [(x, y) for y in range(y0, y1) for x in range(x0, x1)]
    records = []
    def get_tile(xy):
        x, y = xy
        url = template.format(z=zoom, x=x, y=y)
        raw = fetch(url, cache, missing_ok=missing_ok)
        if raw is None:
            return x, y, None, {"url": url, "status": 404}
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
        if im.size != (tile_px, tile_px):
            raise ValueError(f"Unexpected tile size {im.size} {url}")
        return x, y, im, {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for x, y, im, rec in pool.map(get_tile, tasks):
            if im is not None:
                out.paste(im, ((x - x0) * tile_px, (y - y0) * tile_px))
            records.append(rec)
    output = DIST / "assets/geography" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    if filename.endswith(".jpg"):
        if np.asarray(out.getchannel("A")).min() != 255:
            raise ValueError("Cannot silently flatten transparent data gaps into JPEG")
        out.convert("RGB").save(output, quality=92)
    else:
        out.save(output, optimize=True)
    actual = [-180 + x0 * step, 90 - y1 * step, -180 + x1 * step, 90 - y0 * step]
    return {"image": str(output.relative_to(DIST)), "bounds": actual, "width": out.width, "height": out.height,
            "sha256": sha(output), "sampling_m_per_pixel_at_equator": step * DEGREE_M / tile_px,
            "projection": "equirectangular_lonlat", "tile_matrix": zoom, "tile_count": len(records)}, records

def gale_color():
    import rasterio
    from rasterio.enums import Resampling
    output = DIST / "assets/geography/gale-hirise-color.jpg"
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="50"):
        with rasterio.open(GALE_COLOR) as src:
            # Source is explicitly Mars-sphere equirectangular, lon0=0, lat_ts=0.
            if src.count != 3 or src.transform.a != 0.25:
                raise ValueError("Changed source profile: inspect before rebuilding")
            if not output.exists():
                arr = src.read(out_shape=(3, 4324, 2048), resampling=Resampling.average)
                Image.fromarray(arr.transpose(1, 2, 0)).save(output, quality=94)
            bounds = [src.bounds.left / DEGREE_M, src.bounds.bottom / DEGREE_M, src.bounds.right / DEGREE_M, src.bounds.top / DEGREE_M]
            return {"id": "gale-hirise-color", "label": "HiRISE LRGB color mosaic", "role": "detail", "image": str(output.relative_to(DIST)),
                    "bounds": bounds, "width": 2048, "height": 4324, "projection": "equirectangular_lonlat",
                    "source_resolution_m": 0.25, "sampling_m_per_pixel_at_equator": 9000 / 2048,
                    "source_url": GALE_PAGE, "download_url": GALE_COLOR, "source_id": "gale_color",
                    "attribution": "Timothy Parker and Fred J. Calef III; NASA/JPL-Caltech/USGS/UArizona",
                    "sha256": sha(output), "color_kind": "published LRGB fusion",
                    "notes": "Published July 2025 RGB strips fused to the mission RED orthomosaic; source grayscale strips and seams are retained. Colors are an enhanced display mosaic, not an oxide or mineral abundance map."}

def glen_raster(cache):
    raw = fetch(GLEN, cache, "glen-torridon.jpg")
    output = DIST / "assets/geography/glen-torridon-geology.jpg"
    # The archive image is the full map panel. Do not invent new unit outlines or
    # remove cartographic content. Author bounds are only given to four decimals.
    output.write_bytes(raw)
    return {"id": "glen-torridon-fedo2022", "label": "Glen Torridon stratigraphy (Fedo et al., 2022)",
            "image": str(output.relative_to(DIST)), "bounds": [137.3767, -4.7383, 137.3919, -4.7206],
            "width": 2058, "height": 2402, "projection": "equirectangular_lonlat",
            "source_url": "https://doi.org/10.5281/zenodo.7041712", "paper_url": "https://doi.org/10.1029/2022JE007408",
            "sha256": sha(output), "license": "CC BY 4.0", "attribution": "Fedo et al. (2022)",
            "notes": "Published annotated map panel positioned with the authors' four-decimal corner coordinates (several-metre georeferencing precision). Local coverage only; the original yellow traverse, white sample circles, contacts and contours are retained. This raster does not support automatic unit assignment."}

def esri_geometry(rings):
    from shapely.geometry import Polygon, MultiPolygon
    from shapely import make_valid
    # ESRI exterior rings are clockwise, interior rings counterclockwise.
    shells, holes = [], []
    for ring in rings:
        if len(ring) < 4:
            continue
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
        (shells if area < 0 else holes).append(ring)
    if not shells:
        shells, holes = holes, []
    hole_groups = [[] for _ in shells]
    shell_polys = [Polygon(r) for r in shells]
    for h in holes:
        hp = Polygon(h).representative_point()
        owners = [i for i, p in enumerate(shell_polys) if p.covers(hp)]
        if owners:
            hole_groups[min(owners, key=lambda i: shell_polys[i].area)].append(h)
    return make_valid(MultiPolygon([Polygon(r, hole_groups[i]) for i, r in enumerate(shells)]))

def jezero_units(cache, bounds):
    from shapely.geometry import box, mapping
    query = {"where": "1=1", "outFields": "*", "outSR": "104971", "f": "json", "returnGeometry": "true", "geometryPrecision": "6", "resultRecordCount": "2000"}
    url = JEZERO_SERVICE + "/8/query?" + urllib.parse.urlencode(query)
    raw = fetch(url, cache, "jezero_geo.txt")
    doc = json.loads(raw)
    if doc.get("exceededTransferLimit") or doc.get("error") or doc.get("spatialReference", {}).get("wkid") != 104971:
        raise ValueError("Incomplete or incorrect-coordinate Jezero geometry")
    style = json.loads(fetch(JEZERO_SERVICE + "/8?f=pjson", cache, "units.txt"))
    colors = {r["value"]: "#" + "".join(f"{x:02x}" for x in r["symbol"]["color"][:3]) for r in style["drawingInfo"]["renderer"]["uniqueValueInfos"]}
    clip = box(*bounds)
    features, units = [], {}
    for f in doc["features"]:
        a = f["attributes"]
        geom = esri_geometry(f["geometry"]["rings"])
        if not geom.intersects(clip):
            continue
        geom = geom.intersection(clip).simplify(2 / DEGREE_M, preserve_topology=True)
        if geom.is_empty:
            continue
        code = a["symbol"]
        units[code] = {"code": code, "name": a["name"], "color": colors[a["unit"]], "description": a["Unit_Description"],
                       "interpretation_2020": a["Unit_Interpretation"], "additional_characteristics": a["Additional_Characteristics"]}
        features.append({"type": "Feature", "id": a["OBJECTID"], "properties": {"code": code, "name": a["name"], "color": colors[a["unit"]], "source_id": "jezero_sim3464"}, "geometry": mapping(geom)})
    output = DIST / "data/geology/jezero-units.geojson"
    write_json(output, {"type": "FeatureCollection", "name": "USGS SIM3464 Jezero display excerpt", "coordinate_system": "Mars_2000_Sphere geographic east longitude / planetocentric latitude (ESRI:104971); not WGS84", "features": features})
    return {"geojson": str(output.relative_to(DIST)), "label": "USGS Jezero geology · 1:75,000", "units": list(units.values()), "bounds": bounds,
            "feature_count": len(features), "source_feature_count": len(doc["features"]), "source_url": "https://doi.org/10.3133/sim3464",
            "service_url": JEZERO_SERVICE, "source_query": url, "source_sha256": hashlib.sha256(raw).hexdigest(), "sha256": sha(output),
            "attribution": "Sun, V.Z. and Stack, K.M. (2020), USGS SIM3464", "scale": "1:75,000", "license": "USGS public-domain map; web service supplied for viewing purposes only",
            "notes": "Orbital geologic map published before Perseverance landed. Published units and 2020 interpretations are historical mapping hypotheses, not a current mineral classifier. This clipped, ~2 m simplified display excerpt is for viewing; use the linked official PDF/GIS for scientific analysis. Boundaries are approximate at the published map scale."}

def zhurong_geology(cache, bounds):
    import libarchive, subprocess
    from shapely.geometry import shape, box, mapping
    archive_url = "https://zenodo.org/api/records/13341513/files/Southern_Utopia_Zhurong.rar/content"
    fetch(archive_url, cache, "zhurong.rar")
    directory = cache / "zhurong_extracted"
    with libarchive.file_reader(str(cache / "zhurong.rar")) as entries:
        for entry in entries:
            # Extract only these explicitly named, public GIS sources.
            if entry.isfile and ("/Layers/Units/Tianwen_Units." in entry.pathname or "/Layers/LandingSite." in entry.pathname or entry.pathname.endswith("map_readme.txt")):
                destination = directory / entry.pathname
                if not destination.resolve().is_relative_to(directory.resolve()):
                    raise ValueError("Unexpected archive path")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"".join(entry.get_blocks()))
    prefix = directory / "Southern_Utopia_Zhurong/Layers"
    converted = []
    for path, filename in [(prefix / "Units/Tianwen_Units.shp", "zhurong-units-raw.geojson"), (prefix / "LandingSite.shp", "zhurong-landing-raw.geojson")]:
        out = cache / filename
        if not out.exists():
            subprocess.run(["ogr2ogr", "-f", "GeoJSON", "-t_srs", "+proj=longlat +a=3396190 +b=3396190 +no_defs", str(out), str(path)], check=True)
        converted.append(json.loads(out.read_text()))
    colors = {"lHt": "#c3ab7a", "Av": "#c87f6b", "Ah": "#bd9562", "lHlsm": "#70a6b1", "lHldm": "#667fa3"}
    feats, units = [], []
    for f in converted[0]["features"]:
        prop = f["properties"]
        code, name = prop["UnitSymbol"], prop["UnitName"]
        units.append({"code": code, "name": name, "color": colors[code]})
        geom = shape(f["geometry"]).intersection(box(*bounds))
        if geom.is_empty:
            continue
        feats.append({"type": "Feature", "id": prop["OBJECTID"], "properties": {"code": code, "name": name, "color": colors[code], "source_id": "zhurong_wu2024"}, "geometry": mapping(geom.simplify(10 / DEGREE_M, preserve_topology=True))})
    output = DIST / "data/geology/zhurong-units.geojson"
    write_json(output, {"type": "FeatureCollection", "coordinate_system": "Mars_2000_Sphere geographic degrees; not WGS84", "features": feats})
    coords = converted[1]["features"][0]["geometry"]["coordinates"]
    return {"geojson": str(output.relative_to(DIST)), "label": "Southern Utopia regional geology (Wu et al., 2024)", "title": "Southern Utopia regional geology",
            "units": units, "bounds": bounds, "feature_count": len(feats), "source_feature_count": 5,
            "source_url": "https://doi.org/10.5281/zenodo.13341513", "paper_url": "https://doi.org/10.1038/s41598-024-75507-w", "license": "CC BY 4.0", "attribution": "Wu et al. (2024)",
            "source_download": archive_url, "source_sha256": sha(cache / "zhurong.rar"), "sha256": sha(output),
            "notes": "Published regional geomorphic interpretation, not a LIBS mineral map. This local excerpt falls within one regional unit. The source's marine labels are the authors' hypothesis, not a confirmed ocean detection. Original August 2024 archive unit names are retained; age terminology differs from the revised final paper. Display colors are assigned here. Landing position is context only; no LIBS target coordinates are supplied."}, {"name": "Zhurong landing", "lon": coords[0], "lat": coords[1], "source_url": "https://doi.org/10.5281/zenodo.13341513", "position_kind": "author GIS landing point; not LIBS target locations"}

def finalize_metadata(doc):
    from shapely.geometry import shape, box
    for config in doc["missions"].values():
        if config.get("geology"):
            config["geology"].setdefault("title", config["geology"]["label"])
    # Cartographic label positions derived from the actual published polygons.
    # These are not sample or measurement locations.
    features = json.loads((DIST / doc["missions"]["supercam"]["geology"]["geojson"]).read_text())["features"]
    clip = box(77.18, 18.40, 77.50, 18.54)
    labels = []
    for code, name in [("NHjf2", "Western delta · fan 2"), ("Njf", "Jezero floor"), ("cr", "Western crater rim")]:
        geoms = [shape(f["geometry"]).intersection(clip) for f in features if f["properties"]["code"] == code]
        geoms = [g for g in geoms if not g.is_empty and g.area > 0]
        if not geoms:
            continue
        point = max(geoms, key=lambda g: g.area).representative_point()
        labels.append({"name": name, "lon": point.x, "lat": point.y, "source_url": "https://doi.org/10.3133/sim3464", "position_kind": "cartographic label inside published unit polygon, not a measurement", "unit_code": code})
    doc["missions"]["supercam"]["landmarks"] = labels
    return doc

def build(cache):
    cache.mkdir(parents=True, exist_ok=True)
    (DIST / "assets/geography").mkdir(parents=True, exist_ok=True)
    manifest = {}
    broad = {"chemcam": [137.13, -4.95, 137.68, -4.44], "supercam": [77.10, 18.30, 77.59, 18.64], "zhurong": [109.82, 25.01, 110.0, 25.11]}
    basemaps = {}
    for mission, bounds in broad.items():
        image, tiles = tile_mosaic(CTX_GLOBAL, bounds, 9 if mission == "zhurong" else 10, 512, cache / "tiles", mission + "-ctx-context.jpg")
        image.update({"id": mission + "-ctx", "label": "CTX regional terrain (grayscale)", "role": "regional", "source_id": "ctx_murray",
                      "source_url": "https://murray-lab.caltech.edu/CTX/", "attribution": "NASA/JPL/MSSS/Caltech Murray Lab/Esri", "color_kind": "grayscale",
                      "notes": "NASA Mars Trek / Esri display of the Murray Lab beta01 uncontrolled CTX mosaic. Geographic context only: local offsets and mosaic seams can occur. No tint or inferred composition is added."})
        basemaps[mission] = [image]
        manifest[mission + "_ctx_tiles"] = tiles
        print(mission, "regional CTX", image["bounds"], flush=True)
    basemaps["chemcam"].append(gale_color())
    # Broad high-resolution Jezero CTX, followed by partially transparent HiRISE.
    # Both are on the same Mars geographic tile grid.
    detail_bounds = [77.175, 18.39, 77.51, 18.56]
    for layer, label, filename, role in [(JEZERO_CTX, "Jezero CTX orthomosaic", "jezero-ctx.png", "detail"), (JEZERO_HIRISE, "Jezero HiRISE orthomosaic", "jezero-hirise.png", "detail")]:
        template = "https://trek.nasa.gov/tiles/Mars/EQ/" + layer + "/1.0.0/default/default028mm/{z}/{y}/{x}.png"
        img, tiles = tile_mosaic(template, detail_bounds, 13, 256, cache / "tiles", filename, missing_ok=True)
        img.update({"id": layer, "label": label, "role": role, "source_id": "jezero_trn", "source_url": "https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_orthorectified_image_mosaic",
                    "attribution": "USGS Astrogeology; NASA/JPL/UArizona (HiRISE), NASA/JPL/MSSS (CTX); Fergason et al. (2020)", "color_kind": "grayscale",
                    "notes": "Mars 2020 Terrain Relative Navigation product, resampled through NASA Mars Trek. Transparent areas retain the underlying imagery. Grayscale image; geological colors are a separate overlay."})
        basemaps["supercam"].append(img)
        manifest[layer] = tiles
        print(label, "saved", flush=True)
    glen = glen_raster(cache)
    gale_units = [
        {"code": "BPm–Mf", "name": "Blunts Point member, Murray formation", "color": "#a58c73"},
        {"code": "PPm–Mf", "name": "Pettegrove Point member, Murray formation", "color": "#8e9c70"},
        {"code": "Jm–Mf", "name": "Jura member, Murray formation", "color": "#506a91"},
        {"code": "KHm–CSf", "name": "Knockfarril Hill member, Carolyn Shoemaker formation", "color": "#9b71ac"},
        {"code": "Gm–CSf", "name": "Glasgow member, Carolyn Shoemaker formation", "color": "#a4ad57"},
        {"code": "Sf", "name": "Stimson formation", "color": "#83878d"}]
    zh_geology, zh_landing = zhurong_geology(cache, basemaps["zhurong"][0]["bounds"])
    doc = {"schema_version": "1.0", "generated_at_utc": "2026-11-16", "planet": "Mars", "reference_radius_m": RADIUS,
           "coordinate_note": "All image bounds are [west,south,east,north] in east-positive degrees on Mars. Do not pass through Earth Web Mercator/WGS84 transformations. ChemCam rover latitude convention is retained as supplied by its source and is not independently asserted here.",
           "missions": {
               "chemcam": {"name": "Gale crater", "basemaps": basemaps["chemcam"], "geology": {"label": "Glen Torridon published stratigraphy", "rasters": [glen], "units": gale_units, "bounds": glen["bounds"], "source_url": glen["source_url"], "notes": "Local published map only (~0.9 × 1.0 km). Outside this footprint no local geological classification is supplied. Unit swatches are display approximations; the original map is retained."}, "landmarks": [{"name": "Glen Torridon", "lon": 137.3843, "lat": -4.72945, "source_url": glen["source_url"], "position_kind": "label at center of published map extent"}]},
               "supercam": {"name": "Jezero crater", "basemaps": basemaps["supercam"], "geology": jezero_units(cache, [77.10, 18.30, 77.59, 18.64]), "landmarks": []},
               "zhurong": {"name": "Southern Utopia Planitia", "basemaps": basemaps["zhurong"], "geology": zh_geology, "landmarks": [zh_landing]}
           }}
    doc = finalize_metadata(doc)
    write_json(DIST / "data/geography.json", doc)
    write_json(ROOT / "scripts/geography/source_manifest.json", {"tile_sources": manifest, "geography_sha256": sha(DIST / "data/geography.json")})
    print("Wrote geography.json", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=pathlib.Path, default=ROOT / ".cache/geography")
    args = parser.parse_args()
    build(args.cache)
