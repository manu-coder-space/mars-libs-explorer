#!/usr/bin/env python3
"""Build source-linked Raman acquisition and curated evidence layers.

No spectra are classified by this script. Published interpretations are curated
explicitly, and acquisition-only records carry no mineral or organic assignment.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

PROJECT = Path(__file__).resolve().parents[2]
SCAM = 'https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/'
PLACES = 'https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_rover_places/data_localizations/'
SHERLOC = 'https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_sherloc/data_processed/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get(url, path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mars-LIBS-Explorer/1.1 public-PDS-research'})
        with urllib.request.urlopen(req, timeout=60) as response:
            path.write_bytes(response.read())
    return path


def source(sid, title, url, **extra):
    return dict(id=sid, title=title, url=url, **extra)


def read_places(raw):
    output = {}
    for name in ['telemetry', 'best_tactical', 'best_interp']:
        seen = set()
        with (raw / (name + '.csv')).open(encoding='utf-8-sig', newline='') as file:
            for rownum, row in enumerate(csv.DictReader(file), 2):
                if row['frame'] != 'ROVER':
                    continue
                key = int(row['site']), int(row['drive'])
                lat, lon = float(row['planetocentric_latitude']), float(row['longitude'])
                if not (-90 <= lat <= 90 and 0 <= lon <= 360):
                    continue
                loc = dict(lat=lat, lon=lon, site=key[0], drive=key[1], source_id='places_' + name,
                           source_url=PLACES + name + '.csv', source_row=rownum,
                           localization_sol=int(row['sol']), localization_sclk=int(row['sclk']),
                           join='exact_site_drive', kind='rover_position_proxy',
                           latitude_convention='planetocentric', longitude_convention='positive_east_0_360',
                           target_offset_applied=False, position_uncertainty_m=None)
                if name == 'telemetry' and key in seen and output[key]['localization_sclk'] > loc['localization_sclk']:
                    continue
                output[key] = loc
                seen.add(key)
    return output


def mission_points(mission):
    meta = json.loads((PROJECT / 'dist/data' / (mission + '.json')).read_text())
    points = []
    for file in meta['point_files']:
        points.extend(json.loads((PROJECT / 'dist' / file).read_text()))
    return points


def apply_location(record, location, extra=None):
    record.update(lat=location['lat'] if location else None, lon=location['lon'] if location else None,
                  location_kind='rover_position_proxy' if location else 'unlocated',
                  location_provenance=dict(location, **(extra or {})) if location else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True,
                        help='Folder containing supercam/raw and spectroscopy/raw (downloads missing files).')
    args = parser.parse_args()
    raw = args.input_root / 'supercam/raw'
    cache = args.input_root / 'spectroscopy/raw'
    cache.mkdir(parents=True, exist_ok=True)
    sources = [
        source('supercam_masterlist', 'NASA PDS SuperCam observation masterlist', SCAM + 'data_observation_log/m2020_scam_masterlist.csv'),
        source('raman_synthesis_2025', 'Lopez-Reyes et al. (2025), SuperCam Raman activities during the first 1000 sols', 'https://doi.org/10.1029/2025JE008943', doi='10.1029/2025JE008943'),
        source('sharma_2023', 'Sharma et al. (2023), Diverse organic-mineral associations in Jezero crater', 'https://doi.org/10.1038/s41586-023-06143-z', doi='10.1038/s41586-023-06143-z'),
        source('scheller_2024', 'Scheller et al. (2024), Inorganic interpretation of luminescent materials', 'https://doi.org/10.1126/sciadv.adm8241', doi='10.1126/sciadv.adm8241'),
        source('haney_2026', 'Haney et al. (2026), Anhydrite:Ce3+ interpretation of the 304 and 325 nm doublet', 'https://doi.org/10.1029/2025JE009385', doi='10.1029/2025JE009385'),
        source('fornaro_2025', 'Fornaro et al. (2025), Evidence for polycyclic aromatic hydrocarbons in sulfates', 'https://doi.org/10.1038/s41550-025-02638-z', doi='10.1038/s41550-025-02638-z'),
        source('hurowitz_2025', 'Hurowitz et al. (2025), Redox-driven mineral and organic associations', 'https://doi.org/10.1038/s41586-025-09413-0', doi='10.1038/s41586-025-09413-0'),
        source('eigenbrode_2018', 'Eigenbrode et al. (2018), Organic matter preserved in ancient Gale mudstones', 'https://doi.org/10.1126/science.aas9185', doi='10.1126/science.aas9185', open_access_url='https://ntrs.nasa.gov/api/citations/20200001471/downloads/20200001471.pdf'),
        source('freissinet_2025', 'Freissinet et al. (2025), Long-chain alkanes preserved in a Martian mudstone', 'https://doi.org/10.1073/pnas.2420580122', doi='10.1073/pnas.2420580122'),
        source('williams_2026', 'Williams et al. (2026), Diverse organic molecules from the first SAM TMAH experiment', 'https://doi.org/10.1038/s41467-026-70656-0', doi='10.1038/s41467-026-70656-0', open_access_url='https://pmc.ncbi.nlm.nih.gov/articles/PMC13100061/'),
        source('nasa_drill_sols', 'NASA Curiosity rock or soil sampling sites, through November 2016', 'https://science.nasa.gov/resource/curiositys-rock-or-soil-sampling-sites-on-mars-through-november-2016/'),
        source('sherloc_archive', 'NASA PDS SHERLOC archive', 'https://pds-geosciences.wustl.edu/missions/mars2020/sherloc.htm'),
        source('msl_waypoints', 'NASA Curiosity rover waypoints', 'https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json'),
    ]
    master = get(sources[0]['url'], raw / 'm2020_scam_masterlist.csv')
    sources[0].update(sha256=sha(master), bytes=master.stat().st_size)
    for name in ['telemetry', 'best_tactical', 'best_interp']:
        path = get(PLACES + name + '.csv', raw / (name + '.csv'))
        sources.append(source('places_' + name, 'NASA PDS PLACES ' + name, PLACES + name + '.csv', sha256=sha(path), bytes=path.stat().st_size))
    places = read_places(raw)
    grouped = collections.defaultdict(list)
    excluded = []
    all_count = 0
    with master.open(encoding='utf-8-sig', newline='') as file:
        for rownum, row in enumerate(csv.DictReader(file), 2):
            if row['type'] != 'RAMAN':
                continue
            all_count += 1
            if any('scct' in row[key].lower() or 'calibration' in row[key].lower()
                   for key in ['targetname', 'tdb_name', 'Target_Type']):
                excluded.append(rownum)
                continue
            match = re.search(r'ER\d__(\d{3})(\d{4})', row['edr_fname'], re.I)
            if not match:
                raise ValueError('Unrecognized Raman RMC: ' + row['edr_fname'])
            site, drive = map(int, match.groups())
            key = int(row['sol']), row['seqid'].lower(), row['targetname'], site, drive
            grouped[key].append(dict(point=int(row['point_number']), sclk=int(row['sclk']), source_row=rownum,
                                     cdr_filename=row['cdr_fname'], edr_filename=row['edr_fname'],
                                     target_type=row['Target_Type'], gate_archive=row['gate'],
                                     delay_archive=row['delay'], active_coadds=row['actives_ncoadds'],
                                     active_spectra=row['actives_nspectra']))
    acquisitions = []
    for (sol, sequence, target, site, drive), records in sorted(grouped.items()):
        record = dict(id=f'raman-{sol}-{sequence}', mission='Perseverance', mission_key='supercam',
                      category='raman_acquisition', title=target.replace('_', ' '), target=target,
                      sol=sol, sols=[sol], sequence=sequence, point_count=len(set(r['point'] for r in records)),
                      spectrum_count=len(records), method='SuperCam time-resolved Raman',
                      evidence_status='acquisition_only', minerals=[], organic_interpretation=None,
                      summary='Archived Raman acquisition; mineral detection has not been assessed here.',
                      source_ids=['supercam_masterlist'],
                      source_url=SCAM + f'data_calibrated_spectra/sol_{sol:05d}/', records=records)
        apply_location(record, places.get((site, drive)))
        if record['location_provenance']:
            record['source_ids'].append(record['location_provenance']['source_id'])
        acquisitions.append(record)

    observations = []
    by_id = {s['id']: s for s in sources}
    def event(eid, mission, category, target, sol, method, status, summary, source_ids, minerals=None, organic=None, sols=None):
        row = dict(id=eid, mission='Curiosity' if mission == 'chemcam' else 'Perseverance', mission_key=mission,
                   category=category, title=target, target=target, sol=sol, sols=sols or [sol], method=method,
                   evidence_status=status, summary=summary, minerals=minerals or [], organic_interpretation=organic,
                   source_ids=source_ids, source_url=by_id[source_ids[0]]['url'], footprint=None)
        observations.append(row)
        return row

    # Selection of published detections, not an exhaustive mineral catalogue.
    minerals = [
        ('Garde', 209, 'scam01209', ['olivine', 'carbonate'], 'Olivine; carbonate supported by complementary LIBS and infrared observations.'),
        ('Bellegarde', 188, 'scam01188', ['sodium perchlorate'], 'Diagnostic sodium-perchlorate Raman spectrum reported at point 5.'),
        ('Reids Gap', 466, 'scam01466', ['anhydrite II'], 'Strong anhydrite-II Raman signature in a light-toned vein.'),
        ('Solva', 751, 'scam01751', ['olivine', 'carbonate', 'anhydrite'], 'Mixed mineral detections within an abraded patch.'),
        ('Ouzel Falls', 803, 'scam01803', ['olivine', 'carbonate'], 'Olivine and carbonate signatures in the abraded patch.'),
        ('Lake Haiyaha', 853, 'scam01853', ['olivine'], 'Strong olivine Raman doublet in an abraded boulder.'),
        ('Amherst Point', 925, 'scam01925', ['olivine', 'carbonate'], 'Olivine and carbonate detected in the Margin unit.'),
        ('Bills Bay', 940, 'scam01940', ['carbonate', 'calcium sulfate (weak)'], 'Carbonate with a weak calcium-sulfate feature.'),
    ]
    for name, sol, sequence, mineral_list, summary in minerals:
        acquisition = [r for r in acquisitions if r['sol'] == sol and r['sequence'] == sequence]
        assert len(acquisition) == 1, (name, acquisition)
        a = acquisition[0]
        row = event('mineral-' + sequence, 'supercam', 'raman_mineral', name, sol,
                    'SuperCam time-resolved Raman', 'published_mineral_detection', summary,
                    ['raman_synthesis_2025', 'supercam_masterlist'], mineral_list)
        row['acquisition_ids'] = [a['id']]
        row['archive_target'] = a['target']
        row['sequence'] = sequence
        row['data_url'] = a['source_url']
        apply_location(row, a['location_provenance'])

    # Curated SAM sample locations use a named drill-hole/patch observation,
    # retaining its separate observation sol and the original NASA rover proxy.
    chemistry = mission_points('chemcam')
    sam = [
        ('Cumberland', 279, 'sample_collection', 'Cumberland_Hole', 285, (6, 82),
         'SAM GC-MS', 'Decane, undecane and dodecane were detected in the Cumberland sample.',
         ['freissinet_2025', 'nasa_drill_sols'], 'Detected organic compounds; source process unresolved.'),
        ('Confidence Hills', 759, 'sample_collection', 'Confidence_Hills_Full_Drill_Hole', 766, (42, 1020),
         'SAM evolved-gas analysis and GC-MS', 'Sulfur-bearing and other organic pyrolysis products reported in mudstone.',
         ['eigenbrode_2018', 'nasa_drill_sols'], 'Organic matter detected through heating products; biological origin not established.'),
        ('Mojave 2', 882, 'sample_collection', 'Mojave2_FDH_ChemCam', 886, (45, 0),
         'SAM evolved-gas analysis and GC-MS', 'Organic pyrolysis products reported from the Mojave mudstone sample.',
         ['eigenbrode_2018', 'nasa_drill_sols'], 'Organic matter detected through heating products; biological origin not established.'),
        ('Mary Anning 3', 2879, 'SAM_experiment', 'Mary_Anning_3_ccam_2874', 2874, (82, 2176),
         'SAM TMAH thermochemolysis and GC-MS', 'Diverse organic products, including benzothiophene and methyl benzoate, reported after wet chemistry.',
         ['williams_2026'], 'Organic compounds released by derivatization; source process unresolved.'),
    ]
    for name, sol, sol_kind, proxy_target, proxy_sol, site_drive, method, summary, ids, organic in sam:
        matches = [p for p in chemistry if p['target'] == proxy_target and p['sol'] == proxy_sol and p['location']]
        assert matches and {(p['site'], p['drive']) for p in matches} == {site_drive}, name
        point = matches[0]
        row = event('sam-' + re.sub('[^a-z0-9]+', '-', name.lower()), 'chemcam', 'organic_detection', name, sol,
                    method, 'published_organic_detection', summary, ids, organic=organic)
        row['sol_kind'] = sol_kind
        row['source_ids'].append('msl_waypoints')
        apply_location(row, point['location'], dict(join='named_sample_workspace_via_chemcam_target',
                       proxy_target=proxy_target, proxy_observation_sol=proxy_sol, proxy_point_id=point['id'],
                       note='The mapped position is Curiosity at the named sampling workspace; it is not the drill-hole coordinate.'))

    # SHERLOC sol-to-target associations are given by the cited papers. PDS
    # product RMC indices supply an independent exact site/drive location join.
    sh = [
        ('Walhalla Glades', 1180, 'organic_detection', 'published_organic_detection',
         'Raman G-band evidence for organic carbon in Bright Angel mudstone.',
         ['hurowitz_2025'], 'Organic carbon reported from Raman; origin unresolved.', None),
        ('Cheyava Falls', 1201, 'organic_detection', 'published_organic_detection',
         'Raman G-band evidence for organic carbon associated with redox-altered mudstone.',
         ['hurowitz_2025'], 'Organic carbon reported; potential biosignature interpretation does not establish life.', None),
        ('Apollo Temple', 1217, 'organic_detection', 'published_organic_detection',
         'Raman G-band evidence for organic carbon in Bright Angel mudstone.',
         ['hurowitz_2025'], 'Organic carbon reported from Raman; origin unresolved.', None),
        ('Quartier', 293, 'organic_candidate', 'published_organic_interpretation',
         'Sulfate-associated Raman features interpreted as PAHs in a laboratory-analogue study.',
         ['fornaro_2025', 'sharma_2023', 'haney_2026'],
         'Published PAH interpretation. The 304/325 nm fluorescence alone is also explainable by inorganic anhydrite:Ce3+.', [293, 304]),
        ('Pilot Mountain', 874, 'organic_candidate', 'published_organic_interpretation',
         'Sulfate-associated Raman features attributed to PAHs by comparison with laboratory analogues.',
         ['fornaro_2025'], 'Published PAH interpretation; molecular identity and origin require further constraints.', None),
        ('Bellegarde', 186, 'luminescence_unresolved', 'inorganic_alternative_supported',
         'UV fluorescence in sulfate-bearing material; an inorganic cerium-bearing sulfate explanation is supported.',
         ['sharma_2023', 'haney_2026', 'scheller_2024'],
         'Fluorescence measured; this layer does not label it a confirmed organic detection.', None),
    ]
    label_manifest = []
    for name, sol, category, status, summary, ids, organic, sols in sh:
        index = get(SHERLOC + f'sol_{sol:05d}/', cache / f'sherloc_sol_{sol:05d}.html')
        paths = re.findall(r'HREF="([^"]*rm1[^"]*\.xml)"', index.read_text(), re.I)
        # SRLC10000 is the onboard calibration scan and must never place organic
        # calibration material on the surface map.
        paths = [p for p in paths if 'srlc10000' not in p.lower()]
        assert paths, name
        validated = []
        for path in paths:
            url = 'https://pds-geosciences.wustl.edu' + path
            label = get(url, cache / path.rsplit('/', 1)[1])
            root = ET.parse(label).getroot()
            pairs = {}
            for node in root.iter():
                if node.tag.split('}')[-1] == 'Coordinate_Space_Index':
                    values = {c.tag.split('}')[-1]: c.text for c in node}
                    key = values.get('index_id')
                    if key in ('SITE', 'DRIVE'):
                        pairs.setdefault(key, set()).add(int(values['index_value_number']))
            assert len(pairs.get('SITE', [])) == len(pairs.get('DRIVE', [])) == 1, label.name
            site, drive = next(iter(pairs['SITE'])), next(iter(pairs['DRIVE']))
            filename_rmc = re.search(r'rm1__(\d{3})(\d{4})', label.name)
            assert filename_rmc and (site, drive) == tuple(map(int, filename_rmc.groups()))
            item = dict(url=url, sha256=sha(label), bytes=label.stat().st_size, site=site, drive=drive,
                        sol=sol, target_assignment='cited_paper_target_sol', is_calibration=False)
            validated.append(item)
            label_manifest.append(item)
        assert len({(v['site'], v['drive']) for v in validated}) == 1, name
        site, drive = validated[0]['site'], validated[0]['drive']
        row = event('sherloc-' + re.sub('[^a-z0-9]+', '-', name.lower()), 'supercam', category, name, sol,
                    'SHERLOC deep-UV Raman and luminescence', status, summary,
                    ids + ['sherloc_archive'], organic=organic, sols=sols)
        row['data_url'] = SHERLOC + f'sol_{sol:05d}/'
        row['pds_labels'] = validated
        apply_location(row, places.get((site, drive)),
                       dict(rmc_evidence='PDS SHERLOC XML SITE/DRIVE indices; verified against product filename',
                            target_assignment='Paper names the target and observing sol; no label target-name field is assumed.'))
        assert row['lat'] is not None, name

    for row in observations:
        lp = row.get('location_provenance') or {}
        if lp.get('source_id') in by_id and lp['source_id'] not in row['source_ids']:
            row['source_ids'].append(lp['source_id'])

    result = dict(schema_version='1.0', generated_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                  research_date='2026-11-16', sources=sources,
                  summary=dict(curated_observations=len(observations), curated_located=sum(o['lat'] is not None for o in observations),
                               curated_by_mission=dict(collections.Counter(o['mission_key'] for o in observations)),
                               curated_by_category=dict(collections.Counter(o['category'] for o in observations)),
                               raman_archive_rows=all_count, raman_calibration_rows_excluded=len(excluded),
                               raman_science_products=sum(a['spectrum_count'] for a in acquisitions),
                               raman_science_spectra=sum(a['spectrum_count'] for a in acquisitions),
                               raman_acquisition_groups=len(acquisitions),
                               raman_located_groups=sum(a['lat'] is not None for a in acquisitions),
                               raman_sol_min=min(a['sol'] for a in acquisitions), raman_sol_max=max(a['sol'] for a in acquisitions)),
                  notes=[
                      'Symbols locate rover positions or named sampling workspaces, not exact laser footprints or deposit boundaries.',
                      'Acquisition-only Raman records do not imply mineral detection or organics. Curiosity has no Raman instrument; its organic records here are SAM analyses.',
                      'Curated interpretations are selected literature examples, not an exhaustive or uniformly surveyed mineral/organic inventory.',
                      'Organic detections, published organic interpretations and unresolved luminescence are separate evidence classes. None establishes a biological origin.',
                      'The 2024 and 2026 inorganic luminescence interpretations apply to specified UV features; they do not automatically negate independent Raman G-band detections.',
                      'No spatial interpolation, abundance heatmap, absence inference or estimated target polygon is generated.',
                      'Raman product counts enumerate masterlist/FITS product records, not individual shots or coadded spectra within each FITS file. The legacy raman_science_spectra count is a product-record count.',
                      'Curiosity sample-collection/analysis sols and the ChemCam workspace proxy observation sols are recorded separately.',
                  ], observations=observations, raman_acquisitions=acquisitions)
    output = PROJECT / 'dist/data/spectroscopy.json'
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    validation = dict(result['summary'], calibration_source_rows_excluded=excluded,
                      unique_acquisition_ids=len({a['id'] for a in acquisitions}),
                      unique_curated_ids=len({a['id'] for a in observations}),
                      sherloc_label_count=len(label_manifest), sherloc_labels=label_manifest,
                      output_sha256=sha(output), output_bytes=output.stat().st_size,
                      all_finite_coordinates=all(-90 <= a['lat'] <= 90 and 0 <= a['lon'] <= 360
                                                 for a in observations + acquisitions if a['lat'] is not None))
    assert validation['unique_acquisition_ids'] == len(acquisitions)
    assert validation['unique_curated_ids'] == len(observations)
    (PROJECT / 'scripts/spectroscopy/verification.json').write_text(json.dumps(validation, indent=2), encoding='utf-8')
    print(json.dumps(result['summary'], indent=2))
    print(f'Wrote {output.stat().st_size:,} bytes to {output}')


if __name__ == '__main__':
    main()
