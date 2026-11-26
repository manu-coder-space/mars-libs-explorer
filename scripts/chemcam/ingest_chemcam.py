#!/usr/bin/env python3
"""Build a reproducible Curiosity ChemCam composition/rover-context dataset.

Run fetch_sources.py first, then this script. Downloaded official files are cached.
No estimated target coordinates, spatial interpolation, or chemical renormalization.
"""
from __future__ import annotations
import concurrent.futures
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import struct
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path
from fetch_sources import BASE, RAW, ROOT, fetch, moc_inventory, set_workdir

OXIDES = ['SiO2', 'TiO2', 'Al2O3', 'FeOT', 'MgO', 'CaO', 'Na2O', 'K2O', 'MnO']
WAYPOINT_URL = 'https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json'
RMI_NAMES = [
    '0019_crm_ccam01019_mara_1',
    '0022_crm_ccam02022_preble',
    '0045_crm_ccam01045_jake',
    '0135_crm_ccam01135_rapitan',
    '0165_crm_ccam02165_john_klein_rp2',
    '0187_crm_ccam01187_cumberland',
    '0707_crm_ccam03707_stirling_2',
    '1993_crm_ccam01993_stirling_castle__',
    '4044_crm_ccam05043_bighorn_plateau',
    '4842_crm_ccam01842_san_julian',
]

def num(value):
    if value is None:
        return None
    try:
        v = float(str(value).strip())
        return v if math.isfinite(v) and abs(v) < 1e30 and v > -9999 else None
    except (ValueError, TypeError):
        return None

def integer(value):
    v = num(value)
    return int(v) if v is not None and v == int(v) else None

def text(value):
    return str(value).strip() if value is not None else ''

def label_value(label, key):
    m = re.search(r'^\s*' + re.escape(key) + r'\s*=\s*(.+)$', label, re.M)
    return m.group(1).strip().strip('"') if m else None

def collect_sources(inventory):
    sources = {}
    for p in sorted(RAW.glob('*.source.json')):
        meta = json.loads(p.read_text())
        source_file = ROOT / meta['local_file']
        if re.fullmatch(r'moc_\d+_\d+\.(csv|lbl)', source_file.name) and source_file.name not in inventory:
            continue
        assert source_file.is_file(), source_file
        assert hashlib.sha256(source_file.read_bytes()).hexdigest() == meta['sha256'], source_file
        sources[source_file.name] = meta
    return sources

def load_moc_inventory():
    """Require a successful acquisition and use its authoritative product list."""
    manifest = json.loads((ROOT / 'source_manifest.json').read_text())
    if manifest.get('failures'):
        raise ValueError('Source manifest contains acquisition failures; rerun fetch_sources.py successfully.')
    sources = manifest['sources']
    if isinstance(sources, dict):
        sources = list(sources.values())
    by_name = {Path(item['local_file']).name: item for item in sources}
    directory = RAW / 'moc_directory.html'
    directory_source = by_name['moc_directory.html']
    if hashlib.sha256(directory.read_bytes()).hexdigest() != directory_source['sha256']:
        raise ValueError('MOC directory hash differs from the acquisition manifest')
    inventory = moc_inventory(directory.read_text())
    if manifest.get('moc_inventory') is not None and inventory != manifest['moc_inventory']:
        raise ValueError('MOC inventory differs from the acquired directory')
    for name, url in inventory.items():
        meta = by_name.get(name)
        path = RAW / name
        if not meta or meta['url'] != url or not path.is_file():
            raise ValueError('Missing current MOC product: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta['sha256']:
            raise ValueError('MOC product hash differs from acquisition manifest: ' + name)
    return inventory

def download_context(refresh=False):
    tasks = [(WAYPOINT_URL, 'MSL_waypoints.json')]
    tasks += [(BASE + 'extras/rmi_mosaics/' + name + suffix, None)
              for name in RMI_NAMES for suffix in ['.lbl', '.png']]
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        pending = {ex.submit(fetch, u, n, refresh): u for u, n in tasks}
        for f in concurrent.futures.as_completed(pending):
            try:
                f.result()
            except Exception as e:
                failures.append({'url': pending[f], 'error': str(e)})
    if failures:
        print('Context download failures:', json.dumps(failures), flush=True)
    return failures

def load_log():
    log = {}
    duplicates = []
    with (RAW / 'msl_ccam_obs.csv').open(newline='', encoding='utf-8-sig') as f:
        for row_number, row in enumerate(csv.DictReader(f), 2):
            row = {k.strip(): v.strip() for k, v in row.items() if k is not None and isinstance(v, str)}
            sclk = integer(row.get('Spacecraft Clock'))
            if sclk is None:
                continue
            if sclk in log:
                previous = {key: value for key, value in log[sclk].items() if key != '_row'}
                if previous != row:
                    duplicates.append(sclk)
                continue
            row['_row'] = row_number
            log[sclk] = row
    if duplicates:
        raise ValueError('Ambiguous observation-log spacecraft clocks: ' + ', '.join(map(str, sorted(set(duplicates))[:20])))
    return log, duplicates

def load_locations():
    path = RAW / 'MSL_waypoints.json'
    if not path.exists():
        return {}, [], []
    features = json.loads(path.read_text())['features']
    locations = {}
    duplicates = []
    route = []
    for i, f in enumerate(features):
        p = f['properties']
        site, drive = integer(p.get('site')), integer(p.get('drive'))
        lat, lon = num(p.get('lat')), num(p.get('lon'))
        if None in (site, drive, lat, lon):
            continue
        assert -90 <= lat <= 90 and -360 <= lon <= 360
        location = {'lat': lat, 'lon': lon, 'elevation_m': num(p.get('elev_geoid')),
                    'kind': 'rover_position_proxy', 'source': 'MSL_waypoints.json',
                    'source_feature_index': i, 'site': site, 'drive': drive,
                    'sol': integer(p.get('sol')), 'dist_total_m': num(p.get('dist_total_m')),
                    'easting_m': num(p.get('easting')), 'northing_m': num(p.get('northing')),
                    'latitude_convention': 'unspecified_by_source',
                    'longitude_convention': 'east_positive', 'elevation_reference': 'source_elev_geoid'}
        key = (site, drive)
        if key in locations:
            old = locations[key]
            if (old['lat'], old['lon'], old['elevation_m']) != (lat, lon, location['elevation_m']):
                duplicates.append(key)
        locations[key] = location
        route.append(location)
    # An ambiguous exact key must not silently choose one location.
    for key in duplicates:
        locations.pop(key, None)
    return locations, route, duplicates

def calibration_evidence(obs):
    evidence = []
    for key in ['Target Type', 'Target', 'Type of Product', 'Comments']:
        s = text(obs.get(key))
        # Explicit terms; never use substring 'cal' (which matches calcium/vertical).
        if re.search(r'\bcalibration\b|\bccct\b|\bcal[ ._-]*target\b', s, re.I):
            evidence.append({'field': key, 'value': s})
    return evidence

def read_moc(log, locations, inventory):
    points = []
    file_reports = []
    ranges = {}
    for path in (RAW / name for name in sorted(inventory) if name.endswith('.csv')):
        allrows = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
        header_i = next(i for i, r in enumerate(allrows) if len(r) > 2 and text(r[0]).lower() == 'file' and text(r[1]).lower() == 'target')
        header = [text(x) for x in allrows[header_i]]
        for row in allrows[:header_i]:
            if len(row) > 1 and text(row[1]) in ('Min', 'Max'):
                ranges.setdefault(path.name, {})[text(row[1])] = {oxide: num(row[header.index(oxide)]) for oxide in OXIDES}
        label = path.with_suffix('.lbl').read_text()
        declared_rows = integer(label_value(label, 'ROWS'))
        count = 0
        for physical_row, values in enumerate(allrows[header_i + 1:], header_i + 2):
            if not values or not text(values[0]):
                continue
            assert len(values) == len(header), (path.name, physical_row, len(values), len(header))
            row = dict(zip(header, values))
            product = text(row['File']).upper().removesuffix('.CSV')
            match = re.fullmatch(r'CL\d_(\d+)CCS_(.+)', product)
            if not match:
                raise ValueError(f'Unexpected source product {product}')
            sclk = int(match.group(1))
            obs = log.get(sclk, {})
            sol = integer(obs.get('Sol'))
            site = integer(obs.get('RMC Site'))
            drive = integer(obs.get('RMC Drive'))
            pose = integer(obs.get('RMC POSE'))
            flags = []
            if not obs:
                flags.append('observation_log_join_missing')
            cal_evidence = calibration_evidence(obs)
            if cal_evidence:
                flags.append('onboard_calibration_target')
            quality_notes = {}
            for key, flag in [('spectra to ignore', 'archive_ignore_note'),
                              ('Saturation', 'archive_saturation_note'),
                              ('Continuum Removal', 'archive_continuum_note'),
                              ('Heterogeneity', 'archive_heterogeneity_note')]:
                if text(obs.get(key)):
                    quality_notes[key] = text(obs[key])
                    flags.append(flag)
            oxides = {oxide: num(row.get(oxide)) for oxide in OXIDES}
            rmsep = {oxide: num(row.get(oxide + ' RMSEP')) for oxide in OXIDES}
            shot_sd = {oxide: num(row.get(oxide + '_shots_stdev')) for oxide in OXIDES}
            total = num(row.get('Sum of Oxides'))
            distance = num(row.get('Distance (m)'))
            if any(v is not None and v < 0 for v in oxides.values()):
                flags.append('negative_oxide_prediction')
            if any(v is None for v in oxides.values()):
                flags.append('missing_oxide_value')
            if distance is not None and distance > 3.5:
                flags.append('target_distance_above_3p5_m_review_distance_bias')
            if total is not None and (total < 80 or total > 120):
                flags.append('oxide_total_outside_80_to_120_review')
            outside = [o for o in OXIDES if oxides[o] is not None and
                       (oxides[o] < ranges[path.name]['Min'][o] or oxides[o] > ranges[path.name]['Max'][o])]
            if outside:
                flags.append('outside_testset_minmax')
            location = locations.get((site, drive))
            if not location:
                flags.append('rover_waypoint_exact_join_missing')
            # Do not imply a target position: this is only the matching rover waypoint.
            point = {'id': product, 'mission': 'Curiosity', 'instrument': 'ChemCam',
                     'sol': sol, 'sequence': text(obs.get('Sequence')) or None, 'point': None,
                     'point_index_kind': 'not_available', 'target': text(row['Target']),
                     'sclk': sclk, 'site': site, 'drive': drive, 'pose': pose,
                     'distance_m': distance, 'target_type': text(obs.get('Target Type')) or None,
                     'is_calibration': bool(cal_evidence), 'calibration_evidence': cal_evidence,
                     'oxides': oxides, 'uncertainty': {'rmsep': rmsep, 'shot_sd': shot_sd},
                     'total_wt_pct': total, 'spectrum_total': num(row.get('Spectrum Total')),
                     'quality_flags': flags, 'quality_notes': quality_notes,
                     'outside_testset_oxides': outside, 'location': location, 'rmi': [],
                     'source_id': path.name, 'source_row': physical_row,
                     'log_source_row': obs.get('_row'),
                     'spectrum_url': BASE + f'data/sol{sol:05d}/' + product.lower() + '.csv' if sol is not None else None,
                     'spectrum_label_url': BASE + f'data/sol{sol:05d}/' + product.lower() + '.lbl' if sol is not None else None,
                     'observing': {'pattern': text(obs.get('Type of Observation')) or None,
                                   'n_shots_commanded': integer(obs.get('Nbr of Shots')),
                                   'rsm_az_rad': num(obs.get('RSM Az (rad)')),
                                   'rsm_el_rad': num(obs.get('RSM El (rad)')),
                                   'comments': text(obs.get('Comments')) or None}}
            points.append(point)
            count += 1
        assert count == declared_rows, (path.name, count, declared_rows)
        file_reports.append({'file': path.name, 'rows': count, 'declared_rows': declared_rows,
                             'product_version': label_value(label, 'PRODUCT_VERSION_ID'),
                             'product_creation_time': label_value(label, 'PRODUCT_CREATION_TIME'),
                             'release_id': label_value(label, 'RELEASE_ID'),
                             'calibration_header': allrows[0][0], 'testset_ranges': ranges[path.name]})
    # Duplicate products across source tables would require an explicit version policy.
    ids = [p['id'] for p in points]
    assert len(ids) == len(set(ids)), 'Duplicate ChemCam product IDs'
    groups = defaultdict(list)
    for p in points:
        groups[(p['sol'], p['sequence'], p['target'])].append(p)
    for group in groups.values():
        for i, p in enumerate(sorted(group, key=lambda q: q['sclk']), 1):
            p['point'] = i
            p['point_index_kind'] = 'chronological_order_in_sequence_target'
    return sorted(points, key=lambda p: p['sclk']), file_reports

def read_rmi(points):
    lookup = {p['sclk']: p for p in points}
    targets = []
    failures = []
    for name in RMI_NAMES:
        path, img = RAW / (name + '.lbl'), RAW / (name + '.png')
        if not path.exists() or not img.exists():
            continue
        content = path.read_text()
        png = img.read_bytes()
        assert png[:8] == b'\x89PNG\r\n\x1a\n', name
        width, height = struct.unpack('>II', png[16:24])
        annotation_block = re.search(r'MSL:CCAM_ANNOTATION_VALUE\s*=\s*(.*?)\n\s*MSL:CCAM_ANNOTATION_NAME', content, re.S)
        if not annotation_block:
            failures.append({'rmi': name, 'reason': 'No point annotations in label'})
            continue
        tuples = re.findall(r'\(\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', annotation_block.group(1))
        annotated = []
        unmatched = []
        for sclk_, number_, x_, y_ in tuples:
            sclk, number, x, y = int(sclk_), int(number_), float(x_), float(y_)
            assert 0 <= x < width and 0 <= y < height, (name, x, y, width, height)
            point = lookup.get(sclk)
            if not point:
                unmatched.append(sclk)
                continue
            point['point'] = number
            point['point_index_kind'] = 'rmi_annotation'
            point['rmi'].append(name)
            annotated.append({'point_id': point['id'], 'point': number, 'x': x, 'y': y})
        if not annotated:
            failures.append({'rmi': name, 'reason': 'No MOC matches', 'unmatched_sclk': unmatched})
            continue
        first_id = annotated[0]['point_id']
        first = next(p for p in points if p['id'] == first_id)
        targets.append({'id': name, 'mission': 'Curiosity', 'instrument': 'ChemCam',
                        'target': label_value(content, 'MSL:TARGET_NAME') or first['target'],
                        'sol': integer(label_value(content, 'PLANET_DAY_NUMBER')),
                        'sequence': first['sequence'], 'image_url': BASE + 'extras/rmi_mosaics/' + name + '.png',
                        'image_local_path': str(img.relative_to(ROOT)),
                        'label_url': BASE + 'extras/rmi_mosaics/' + name + '.lbl',
                        'width': width, 'height': height,
                        'coordinate_method': 'official_PDS_RMI_mosaic_label_annotations_joined_by_SCLK',
                        'coordinate_uncertainty_px': None,
                        'coordinate_frame': 'image_top_left_x_right_y_down',
                        'pixel_index_base': 'as_provided_in_source_label',
                        'coordinate_note': 'Mosaic pixel annotation; positioning uncertainty not specified by label.',
                        'points': annotated, 'unmatched_sclk': unmatched,
                        'source_id': name + '.lbl', 'image_credit': 'NASA/JPL-Caltech/LANL/CNES/IRAP'} )
    return targets, failures

def main():
    global ROOT, RAW
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, default=Path(__file__).resolve().parent,
                        help='Source cache and output directory; use the same value as fetch_sources.py.')
    parser.add_argument('--offline', action='store_true', help='Rebuild using only cached products; do not request any online context files.')
    parser.add_argument('--refresh-context', action='store_true', help='Check rover locations and selected RMI products for remote updates.')
    args = parser.parse_args()
    if args.offline and args.refresh_context:
        parser.error('--offline and --refresh-context are mutually exclusive')
    ROOT = args.workdir.resolve()
    RAW = ROOT / 'raw'
    set_workdir(ROOT)
    inventory = load_moc_inventory()
    failures = [] if args.offline else download_context(refresh=args.refresh_context)
    if failures:
        raise RuntimeError('Context acquisition failed; no new dataset was generated: ' + json.dumps(failures))
    log, duplicate_log = load_log()
    locations, route, ambiguous_waypoints = load_locations()
    points, file_reports = read_moc(log, locations, inventory)
    rmi_targets, rmi_failures = read_rmi(points)
    sources = collect_sources(inventory)
    for item in file_reports:
        sources[item['file']].update({k: v for k, v in item.items() if k != 'file'})
    valid_sols = [p['sol'] for p in points if p['sol'] is not None]
    science = [p for p in points if not p['is_calibration']]
    geographic = [p for p in science if p['location'] is not None]
    unique_locations = {(p['site'], p['drive']) for p in geographic}
    summary = {'point_count': len(points), 'science_point_count': len(science),
               'calibration_point_count': len(points) - len(science),
               'min_sol': min(valid_sols), 'max_sol': max(valid_sols),
               'target_count': len({(p['sol'], p['sequence'], p['target']) for p in science}),
               'geolocated_science_point_count': len(geographic),
               'geolocated_science_location_count': len(unique_locations),
               'unlocated_science_point_count': len(science) - len(geographic),
               'rmi_target_count': len(rmi_targets), 'rmi_point_count': sum(len(t['points']) for t in rmi_targets),
               'moc_file_count': len(file_reports), 'log_row_count': len(log),
               'quality_flag_counts': dict(Counter(flag for p in points for flag in p['quality_flags']))}
    notes = [
        'Abundances are original archived MOC predictions in oxide wt%; no normalization to 100% has been applied.',
        'FeOT means total iron reported as FeO equivalent; it does not measure iron oxidation state.',
        'RMSEP estimates prediction error from calibration testing; shot SD describes shot-to-shot variability. Neither is silently interpreted as a 95% confidence interval.',
        'Geographic markers are rover waypoint proxies joined by exact site and drive. The actual laser spot can be meters away. No target latitude/longitude was reconstructed.',
        'Unmatched site/drive locations remain null and are still available in chemistry and sol views.',
        'NASA MMGIS latitude convention is unspecified in the downloaded GeoJSON. Raw geographic coordinates are preserved.',
        'Map traverse and chemistry have different release cutoffs. The route may extend beyond the latest archived chemistry.',
        'Onboard calibration targets are flagged using explicit Calibration Target/Cal Target/CCCT terms in observation-log metadata; default science views should exclude these points.',
        'Point numbers outside the curated RMI subset are chronological order within sequence and target, not guaranteed official raster numbers.',
        'RMI annotations are original NASA PDS mosaic pixel coordinates, linked to chemistry by spacecraft clock. Unsampled image areas have no measured LIBS composition.',
        'Range above 3.5 m, testset limits and oxide totals are review flags, not automatic invalidation criteria. Archived quality notes remain available.',
        'Zeros and negative predictions are retained. No missing value or detection limit is replaced with a measured concentration.'
    ]
    data = {'schema_version': '1.0', 'mission': 'Curiosity', 'instrument': 'ChemCam',
            'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'archive_version': {'dataset_id': 'MSL-M-CHEMCAM-LIBS-4/5-RDR-V1.0',
                                'latest_moc_file': file_reports[-1]['file'],
                                'calibration_headers': sorted({r['calibration_header'] for r in file_reports})},
            'oxides': OXIDES, 'units': 'oxide wt%', 'summary': summary, 'sources': sources,
            'notes': notes, 'points': points, 'rmi_targets': rmi_targets, 'traverse': route}
    out = ROOT / 'data.json'
    out.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False))
    (ROOT / 'sample_record.json').write_text(json.dumps(next(p for p in points if p['sclk'] == 399178818), indent=2))
    qa = {'summary': summary, 'source_file_count': len(sources),
          'source_bytes_sha256_verified': True, 'moc_row_counts_match_labels': True,
          'duplicate_product_ids': 0, 'duplicate_log_sclks': duplicate_log,
          'ambiguous_waypoint_keys': ambiguous_waypoints, 'download_failures': failures,
          'rmi_failures': rmi_failures, 'json_bytes': out.stat().st_size,
          'moc_file_reports': file_reports}
    # Known spot is checked against the original official MOC CSV, not synthesized data.
    check = next(p for p in points if p['sclk'] == 399178818)
    assert check['sol'] == 19 and check['target'] == 'Mara_1'
    assert check['oxides']['SiO2'] == 51.5 and check['uncertainty']['rmsep']['SiO2'] == 5
    assert check['uncertainty']['shot_sd']['SiO2'] == .5
    assert check['location']['site'] == 3 and check['location']['drive'] == 78
    assert check['rmi'] == ['0019_crm_ccam01019_mara_1']
    assert next(p for p in points if p['sclk'] == 398646038)['is_calibration']
    assert all(p['is_calibration'] is False for p in points if p['target_type'] and 'vertical' in p['target_type'].lower())
    qa['representative_checks_passed'] = True
    qa['unlocated_science_retained_in_points'] = sum(not p['is_calibration'] and p['location'] is None for p in points)
    qa['rmi_coordinates_within_original_image_bounds'] = all(0 <= p['x'] < t['width'] and 0 <= p['y'] < t['height'] for t in rmi_targets for p in t['points'])
    (ROOT / 'qa_report.json').write_text(json.dumps(qa, indent=2))
    (ROOT / 'source_manifest.json').write_text(json.dumps({'sources': sources, 'moc_inventory': inventory, 'failures': failures}, indent=2))
    findings = 'CHEMCAM INGEST FINDINGS\n\n' + json.dumps(summary, indent=2) + '\n\n' + '\n'.join('- '+n for n in notes)
    findings += '\n\nRun: python fetch_sources.py; python ingest_chemcam.py\nAll source files are cached in raw/ with adjacent SHA256 source metadata.\n'
    (ROOT / 'findings.txt').write_text(findings)
    print(json.dumps({**summary, 'json_megabytes': round(out.stat().st_size / 1e6, 2), 'rmi_failures': rmi_failures}, indent=2), flush=True)

if __name__ == '__main__':
    main()
