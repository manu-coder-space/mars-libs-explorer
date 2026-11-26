#!/usr/bin/env python3
"""Validate context assets and source semantics without pinning NASA release counts."""
import collections
import hashlib
import json
import math
import re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'dist'


def read(path):
    return json.loads((D / path).read_text())


def good(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def valid_location(row):
    lat, lon = row.get('lat'), row.get('lon')
    if lat is None or lon is None:
        assert lat is None and lon is None, row['id']
        assert row['category'] == 'raman_acquisition', row['id']
        assert row.get('location_kind') == 'unlocated' and row.get('location_provenance') is None, row['id']
        return False
    assert good(lat) and good(lon) and -90 <= lat <= 90 and 0 <= lon <= 360, row['id']
    provenance = row.get('location_provenance')
    assert isinstance(provenance, dict), row['id']
    if row['mission_key'] == 'chemcam':
        assert provenance.get('source') == 'MSL_waypoints.json' and 'msl_waypoints' in row['source_ids'], row['id']
        assert provenance.get('proxy_point_id') and provenance.get('join') == 'named_sample_workspace_via_chemcam_target', row['id']
    else:
        assert provenance.get('source_url', '').startswith('https://'), row['id']
    assert provenance.get('lat') == lat and provenance.get('lon') == lon, row['id']
    assert row.get('location_kind') == 'rover_position_proxy', row['id']
    return True


def main():
    geo = read('data/geography.json')
    spec = read('data/spectroscopy.json')
    zhurong = read('data/zhurong.json')
    assert geo['planet'] == 'Mars' and geo['reference_radius_m'] == 3396190
    assets = []
    for mission, context in geo['missions'].items():
        geology = context.get('geology') or {}
        for raster in context['basemaps'] + geology.get('rasters', []):
            path = D / raster['image']
            Image.open(path).verify()
            west, south, east, north = raster['bounds']
            assert all(map(good, raster['bounds'])) and west < east and south < north
            assert -90 <= south <= 90 and -90 <= north <= 90
            assert raster.get('projection') == 'equirectangular_lonlat'
            if raster.get('sha256'):
                assert hashlib.sha256(path.read_bytes()).hexdigest() == raster['sha256'], path
            assets.append(raster['image'])
        if geology.get('geojson'):
            path = D / geology['geojson']
            obj = json.loads(path.read_text())
            assert obj['type'] == 'FeatureCollection'
            assert len(obj['features']) == geology['feature_count']
            if geology.get('sha256'):
                assert hashlib.sha256(path.read_bytes()).hexdigest() == geology['sha256']
            assert all(f['geometry']['type'] in ('Polygon', 'MultiPolygon') for f in obj['features'])

    curated = spec['observations']
    acquisitions = spec['raman_acquisitions']
    rows = curated + acquisitions
    assert len({r['id'] for r in rows}) == len(rows)
    source_ids = {s['id'] for s in spec['sources']}
    assert len(source_ids) == len(spec['sources'])
    for row in rows:
        assert row['mission_key'] in ['chemcam', 'supercam']
        valid_location(row)
        assert row.get('footprint') is None
        assert row['source_ids'] and set(row['source_ids']).issubset(source_ids)
        assert row['source_url'].startswith('https://')
        if row['category'] == 'raman_acquisition':
            assert row['mission_key'] == 'supercam'
            assert row['evidence_status'] == 'acquisition_only' and not row['minerals']
            assert row.get('organic_interpretation') is None
            assert row['records'] and row['spectrum_count'] == len(row['records'])
            assert row['point_count'] == len({r['point'] for r in row['records']})
            assert 'supercam_masterlist' in row['source_ids']
            provenance = row.get('location_provenance')
            for record in row['records']:
                assert isinstance(record['source_row'], int) and record['source_row'] >= 2
                assert record['cdr_filename'] and record['edr_filename']
                assert 'scct' not in row['target'].lower() and 'calibration' not in row['target'].lower()
                assert 'calibration' not in record.get('target_type', '').lower()
                match = re.search(r'ER\d__(\d{3})(\d{4})', record['edr_filename'], re.I)
                assert match, record['edr_filename']
                if provenance:
                    assert provenance['join'] == 'exact_site_drive'
                    assert provenance['source_id'] in row['source_ids']
                    assert tuple(map(int, match.groups())) == (provenance['site'], provenance['drive'])
    summary = spec['summary']
    products = sum(len(r['records']) for r in acquisitions)
    assert products == summary['raman_science_products']
    if 'raman_science_spectra' in summary:
        assert summary['raman_science_spectra'] == products  # Legacy name counts product records.
    assert summary['raman_archive_rows'] == products + summary['raman_calibration_rows_excluded']
    assert summary['raman_acquisition_groups'] == len(acquisitions)
    assert summary['raman_located_groups'] == sum(r['lat'] is not None for r in acquisitions)
    assert summary['curated_observations'] == len(curated)
    assert summary['curated_located'] == sum(r['lat'] is not None for r in curated)
    assert summary['curated_by_category'] == dict(collections.Counter(r['category'] for r in curated))
    assert summary['curated_by_mission'] == dict(collections.Counter(r['mission_key'] for r in curated))
    if acquisitions:
        assert summary['raman_sol_min'] == min(r['sol'] for r in acquisitions)
        assert summary['raman_sol_max'] == max(r['sol'] for r in acquisitions)
    source_rows = [r['source_row'] for a in acquisitions for r in a['records']]
    assert len(source_rows) == len(set(source_rows)), 'Raman source row was assigned twice'

    for table in zhurong['peak_tables']:
        assert (D / table['download_url']).exists()
        assert all(r['location'] is None and 'oxides' not in r for r in table['rows'])
        assert all(c['label'] and c['unit'] for c in table['columns'])
    wavelengths = zhurong['swir']['wavelength_nm']
    # Integrity contract for the pinned Zhang 2025 SWIR supplement, not a general instrument grid.
    assert len(wavelengths) == 309 and wavelengths[0] == 850 and wavelengths[-1] == 2390
    assert all(b - a == 5 for a, b in zip(wavelengths, wavelengths[1:]))
    assert all(len(r['reflectance']) == len(wavelengths) and r['location'] is None for r in zhurong['swir']['spectra'])
    assert not zhurong['chemistry_available'] and not zhurong['raman_available']

    coverage = {}
    warnings = []
    for mission in ('chemcam', 'supercam'):
        meta = read('data/' + mission + '.json')
        bounds = [r['bounds'] for r in geo['missions'][mission]['basemaps']]
        counts = collections.Counter()
        outside_examples = []
        for chunk in meta['point_files']:
            for point in read(chunk):
                if point['is_calibration']:
                    continue
                counts['science_points'] += 1
                location = point.get('location')
                if not location:
                    counts['unlocated_science_points'] += 1
                    continue
                lat, lon = location['lat'], location['lon']
                assert good(lat) and good(lon) and -90 <= lat <= 90 and 0 <= lon <= 360, point['id']
                counts['geolocated_science_points'] += 1
                if any(w <= lon <= e and s <= lat <= n for w, s, e, n in bounds):
                    counts['inside_imagery_bounds'] += 1
                else:
                    counts['outside_imagery_bounds'] += 1
                    if len(outside_examples) < 20:
                        outside_examples.append({'id': point['id'], 'lat': lat, 'lon': lon, 'sol': point['sol']})
        coverage[mission] = {key: counts[key] for key in ('science_points', 'unlocated_science_points', 'geolocated_science_points', 'inside_imagery_bounds', 'outside_imagery_bounds')}
        coverage[mission]['outside_examples'] = outside_examples
        if counts['outside_imagery_bounds']:
            warnings.append(f"{mission}: {counts['outside_imagery_bounds']} science points lie outside bundled imagery bounds; obtain real additional coverage before claiming a complete terrain backdrop.")
    if summary['raman_located_groups'] < len(acquisitions):
        warnings.append('Unlocated Raman acquisitions remain in the catalogue and are omitted from the map.')

    html = (D / 'index.html').read_text()
    assert html == (D / 'mars-libs.html').read_text()
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for filename in ['app.js', 'atlas.js']:
        for element in re.findall(r"\$\('([a-z][a-z0-9-]+)'\)", (D / filename).read_text()):
            assert element in ids or element == 'geology-opacity', (filename, element)
    report = {
        'status': 'passed', 'geographic_images': len(assets), 'curated_evidence': len(curated),
        'raman_observation_groups': len(acquisitions), 'raman_product_records': products,
        'raman_unlocated_groups': len(acquisitions) - summary['raman_located_groups'],
        'zhurong_libs_tables': len(zhurong['peak_tables']),
        'zhurong_table_rows': sum(len(t['rows']) for t in zhurong['peak_tables']),
        'zhurong_swir_spectra': len(zhurong['swir']['spectra']), 'zhurong_swir_wavelengths': len(wavelengths),
        'zhurong_fabricated_locations': 0, 'html_ids': len(ids), 'imagery_coverage': coverage,
        'warnings': warnings,
        'notes': ['Raman counts are checked against current archive metadata rather than a frozen release.',
                  'Imagery coverage uses raster bounds, not per-pixel valid-data masks; grayscale regional context backs transparent detail tiles.',
                  'Scientific ratio endmembers checked separately with node scripts/check_chemistry.cjs',
                  'Independent source-row/checksum validations retained under scripts/geography, scripts/spectroscopy and scripts/zhurong.'],
    }
    (ROOT / 'CONTEXT_VALIDATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
